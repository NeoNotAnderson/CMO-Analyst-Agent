"""
Django REST Framework API Views

All views are skeleton implementations with TODOs.
You will implement the actual logic.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from core.models import Prospectus
from .serializers import (
    UserSerializer,
    ProspectusSerializer,
    ChatMessageSerializer,
    UploadResponseSerializer
)
from agents.parsing_agent.graph import run_agent
import threading
import uuid
from datetime import datetime

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login endpoint

    For mock demo: accepts username without password
    For production: should verify username AND password
    """
    username = request.data.get('username')
    password = request.data.get('password')  # Optional for mock, required for production

    if not username:
        return Response(
            {'error': 'Username is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Try to get existing user
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # For production: verify password
    # if not user.check_password(password):
    #     return Response(
    #         {'error': 'Invalid credentials'},
    #         status=status.HTTP_401_UNAUTHORIZED
    #     )

    # Get or create auth token for the authenticated user
    token, _ = Token.objects.get_or_create(user=user)

    # Serialize user data
    user_serializer = UserSerializer(user)

    return Response({
        'user': user_serializer.data,
        'token': token.key
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])  # User must be authenticated to logout
def logout_view(request):
    """
    Logout endpoint

    Deletes the user's authentication token.
    Requires valid token in Authorization header.
    """
    try:
        # Get the user's token from the request
        # request.auth is automatically populated by TokenAuthentication
        request.auth.delete()

        return Response(
            {'message': 'Successfully logged out'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': 'Logout failed'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get current authenticated user

    TODO: Implement get current user logic

    Steps:
    1. Get user from request.user
    2. Serialize user data
    3. Return user data

    Expected Response:
    {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com"
    }
    """
    user_serializer = UserSerializer(request.user)

    return Response({
        'user': user_serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_prospectus(request):
    """
    Upload prospectus PDF and trigger parsing agent

    Expected Request:
    FormData with 'file' field containing PDF

    Expected Response:
    {
        "prospectus_id": "uuid",
        "prospectus_name": "filename.pdf",
        "status": "pending",
        "message": "Upload successful, parsing started"
    }
    """
    # Validate file exists in request
    file = request.FILES.get('file')
    if not file:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate file is PDF
    if not file.name.endswith('.pdf'):
        return Response(
            {'error': 'Only PDF files are accepted'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create Prospectus object
    prospectus = Prospectus.objects.create(
        prospectus_name=file.name,
        prospectus_file=file,
        created_by=request.user,
        parse_status='pending'
    )

    def parse_in_background():
        try:
            run_agent(prospectus)
        except Exception as e:
            prospectus.parse_status = 'failed'
            prospectus.save()
    
    thread = threading.Thread(target=parse_in_background)
    thread.daemon = True
    thread.start()

    return Response({
        'prospectus_id': str(prospectus.prospectus_id),
        'prospectus_name': prospectus.prospectus_name,
        'status': prospectus.parse_status,
        'message': 'Upload successful, parsing will start when agent is implemented'
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prospectus_list(request):
    """
    Get list of all prospectuses for current user

    Steps:
    1. Query Prospectus.objects.filter(created_by=request.user)
    2. Serialize queryset
    3. Return serialized data

    Expected Response:
    [
        {
            "prospectus_id": "uuid",
            "prospectus_name": "filename.pdf",
            "upload_date": "2024-01-01T00:00:00Z",
            "parse_status": "completed"
        },
        ...
    ]
    """
    files = Prospectus.objects.filter(created_by=request.user)
    serializer = ProspectusSerializer(files, many=True)
    return Response(
        serializer.data,
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prospectus_status(request, prospectus_id):
    """
    Get parsing status for a specific prospectus

    Steps:
    1. Get Prospectus object by prospectus_id
    2. Check if user is authorized (prospectus.created_by == request.user)
    3. Return parse_status and optional progress info

    Expected Response:
    {
        "status": "parsing_index",
        "progress": 25
    }
    """
    try:
        file = Prospectus.objects.get(prospectus_id=prospectus_id)
    except Prospectus.DoesNotExist:
        return Response(
            {'error': 'Prospectus not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    if file.created_by != request.user:
        return Response(
            {'error': "current user does not have access to this file"},
            status=status.HTTP_403_FORBIDDEN
        )
    return Response(
        {'status': str(file.parse_status)},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_chat_message(request):
    """
    Send chat message and get agent response

    Steps:
    1. Get prospectus_id and message from request.data
    2. Validate prospectus exists and user has access
    3. Process message with query agent (future implementation)
    4. For now, return a mock response
    5. Save conversation to database (future)
    6. Return agent response

    Expected Request:
    {
        "prospectus_id": "uuid",
        "message": "What is the deal structure?"
    }

    Expected Response:
    {
        "id": "msg_123",
        "role": "assistant",
        "content": "The deal structure is...",
        "timestamp": "2024-01-01T00:00:00Z",
        "prospectus_id": "uuid"
    }
    """
    
    message = request.data.get('message')
    if not message:
        return Response(
            {'error': "message missing in the input"},
            status=status.HTTP_400_BAD_REQUEST
        )
    prospectus_id = request.data.get('prospectus_id')
    if not prospectus_id:
        return Response(
            {'error': "prospectus_id missing in the input"},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        file = Prospectus.objects.get(prospectus_id=prospectus_id)
    except Prospectus.DoesNotExist:
        return Response(
            {'error': 'Prospectus not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    if file.created_by != request.user:
        return Response(
            {'error': "current user does not have access to this file"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Mock response for now
    response_message = {
        'id': str(uuid.uuid4()),
        'role': 'assistant',
        'content': f'This is a mock response to: {message}. Query agent not implemented yet.',
        'timestamp': datetime.now().isoformat(),
        'prospectus_id': prospectus_id
    }

    return Response(response_message)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request, prospectus_id):
    """
    Get chat history for a prospectus

    Steps:
    1. Validate prospectus exists and user has access
    2. Query chat messages for this prospectus (future: from database)
    3. For now, return empty array
    4. Return serialized messages

    Expected Response:
    {
        "prospectus_id": "uuid",
        "messages": [
            {
                "id": "msg_1",
                "role": "user",
                "content": "Question?",
                "timestamp": "2024-01-01T00:00:00Z"
            },
            {
                "id": "msg_2",
                "role": "assistant",
                "content": "Answer...",
                "timestamp": "2024-01-01T00:00:01Z"
            }
        ]
    }

    Mock Implementation (for now):
    return Response({
        'prospectus_id': prospectus_id,
        'messages': []  # Empty for now, will store in DB later
    })
    """
    try:
        file = Prospectus.objects.get(prospectus_id=prospectus_id)
    except Prospectus.DoesNotExist:
        return Response(
            {'error': 'Prospectus not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.user != file.created_by:
        return Response(
            {'error': 'current user does not have access to this file'},
            status=status.HTTP_403_FORBIDDEN
        )
    #Mock Implementation (for now):
    return Response({
        'prospectus_id': prospectus_id,
        'messages': []  # Empty for now, will store in DB later
    })
