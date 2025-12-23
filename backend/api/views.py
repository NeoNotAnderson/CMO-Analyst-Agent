"""
Django REST Framework API Views

All views are skeleton implementations with TODOs.
You will implement the actual logic.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.contrib.auth.models import User
from core.models import Prospectus
from .serializers import (
    UserSerializer,
    ProspectusSerializer,
    ChatMessageSerializer,
    UploadResponseSerializer
)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Mock login endpoint

    TODO: Implement mock authentication logic

    Steps:
    1. Get username from request.data (should be 'testuser')
    2. Get or create the testuser User object
    3. Generate/retrieve auth token (use Django's Token authentication or JWT)
    4. Return user data and token

    Expected Request:
    {
        "username": "testuser"
    }

    Expected Response:
    {
        "user": {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com"
        },
        "token": "abc123..."
    }
    """
    return Response(
        {'error': 'TODO: Implement login_view'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['POST'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
def logout_view(request):
    """
    Logout endpoint

    TODO: Implement logout logic

    Steps:
    1. Delete user's auth token (if using token auth)
    2. Return success response
    """
    return Response(
        {'message': 'TODO: Implement logout_view'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['GET'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
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
    return Response(
        {'error': 'TODO: Implement get_current_user'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['POST'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
def upload_prospectus(request):
    """
    Upload prospectus PDF and trigger parsing agent

    TODO: Implement prospectus upload logic

    Steps:
    1. Get file from request.FILES['file']
    2. Get filename from request.data or file.name
    3. Create Prospectus object:
       - prospectus_name = filename
       - prospectus_file = file
       - created_by = request.user
       - parse_status = 'pending'
    4. Save to database
    5. Import and call run_agent(prospectus) from agents.parsing_agent.graph
    6. Return prospectus_id and status

    Expected Request:
    FormData with 'file' field containing PDF

    Expected Response:
    {
        "prospectus_id": "uuid",
        "prospectus_name": "filename.pdf",
        "status": "pending",
        "message": "Upload successful, parsing started"
    }

    Example Implementation:
    from agents.parsing_agent.graph import run_agent
    import threading

    file = request.FILES.get('file')
    prospectus = Prospectus.objects.create(
        prospectus_name=file.name,
        prospectus_file=file,
        created_by=request.user,
        parse_status='pending'
    )

    # Run parsing agent in background thread
    def parse_in_background():
        run_agent(prospectus)

    thread = threading.Thread(target=parse_in_background)
    thread.start()

    return Response({
        'prospectus_id': prospectus.prospectus_id,
        'prospectus_name': prospectus.prospectus_name,
        'status': prospectus.parse_status,
        'message': 'Upload successful, parsing started'
    })
    """
    return Response(
        {'error': 'TODO: Implement upload_prospectus'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['GET'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
def get_prospectus_list(request):
    """
    Get list of all prospectuses for current user

    TODO: Implement get prospectus list logic

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
    return Response(
        {'error': 'TODO: Implement get_prospectus_list'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['GET'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
def get_prospectus_status(request, prospectus_id):
    """
    Get parsing status for a specific prospectus

    TODO: Implement get prospectus status logic

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
    return Response(
        {'error': 'TODO: Implement get_prospectus_status'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['POST'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
def send_chat_message(request):
    """
    Send chat message and get agent response

    TODO: Implement chat message logic

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

    Mock Implementation (for now):
    import uuid
    from datetime import datetime

    prospectus_id = request.data.get('prospectus_id')
    message = request.data.get('message')

    # TODO: Later, call query agent here

    # Mock response for now
    response_message = {
        'id': str(uuid.uuid4()),
        'role': 'assistant',
        'content': f'This is a mock response to: {message}. Query agent not implemented yet.',
        'timestamp': datetime.now().isoformat(),
        'prospectus_id': prospectus_id
    }

    return Response(response_message)
    """
    return Response(
        {'error': 'TODO: Implement send_chat_message'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )


@api_view(['GET'])
@permission_classes([AllowAny])  # TODO: Change to IsAuthenticated after implementing auth
def get_chat_history(request, prospectus_id):
    """
    Get chat history for a prospectus

    TODO: Implement get chat history logic

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
    return Response(
        {'error': 'TODO: Implement get_chat_history'},
        status=status.HTTP_501_NOT_IMPLEMENTED
    )
