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

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

# Global session store (in-memory for MVP, replace with Django session/DB later)
_SESSION_STORE = {}


def initialize_user_session(session_id: str) -> str:
    """
    Initialize a new user session.

    This is called by the API when a user logs in.

    Args:
        session_id: Unique session identifier (can be user_id or session token)

    Returns:
        str: Confirmation message with session details
    """
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = {
            'active_prospectus_id': None,
            'active_prospectus_name': None,
            'conversation_history': []
        }
        return f"Session {session_id} initialized. No active prospectus set. You can ask general CMO questions or specify a prospectus to query."
    else:
        active = _SESSION_STORE[session_id].get('active_prospectus_name', 'None')
        return f"Session {session_id} already exists. Active prospectus: {active}"


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
    Optional 'overwrite' field (boolean) if confirming overwrite

    Expected Response:
    {
        "prospectus_id": "uuid",
        "prospectus_name": "filename.pdf",
        "status": "pending",
        "message": "Upload successful, parsing started"
    }
    OR if duplicate found:
    {
        "duplicate": true,
        "prospectus_name": "filename.pdf",
        "message": "A prospectus with this name already exists. Overwrite?"
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

    # Check if prospectus with same name already exists for this user
    existing_prospectus = Prospectus.objects.filter(
        prospectus_name=file.name,
        created_by=request.user
    ).first()

    # Get user's choice: 'use_existing' or leave empty for prompt
    use_existing = request.data.get('use_existing', 'false').lower() == 'true'

    if existing_prospectus and not use_existing:
        # Duplicate found, ask user what to do
        return Response(
            {
                'duplicate': True,
                'prospectus_id': str(existing_prospectus.prospectus_id),
                'prospectus_name': file.name,
                'parse_status': existing_prospectus.parse_status,
                'message': 'A prospectus with this name already exists. Do you want to use the existing one?'
            },
            status=status.HTTP_409_CONFLICT
        )

    # Determine which prospectus to use
    if existing_prospectus and use_existing:
        # User chose to use existing prospectus
        prospectus = existing_prospectus
        message = 'Using existing prospectus, re-parsing in background'
    else:
        # Create new Prospectus object (no existing file or user uploaded different file)
        prospectus = Prospectus.objects.create(
            prospectus_name=file.name,
            prospectus_file=file,
            created_by=request.user,
            parse_status='pending'
        )
        message = 'Upload successful, parsing started in background'

    # Parse in background for both existing and new prospectuses
    def parse_in_background():
        try:
            prospectus.parse_status = 'parsing_index'
            prospectus.save()
            run_agent(prospectus)
        except Exception as e:
            prospectus.parse_status = 'failed'
            prospectus.save()
            print(f"[ERROR] Parsing failed: {e}")

    thread = threading.Thread(target=parse_in_background)
    thread.daemon = True
    thread.start()

    return Response({
        'prospectus_id': str(prospectus.prospectus_id),
        'prospectus_name': prospectus.prospectus_name,
        'status': prospectus.parse_status,
        'message': message
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
def initialize_session(request):
    """
    Initialize a new query session for the user.

    This should be called when the user first accesses the chat interface.
    It creates a session ID and initializes the query agent session.

    Expected Request:
    {
        # No required fields - session is created automatically
    }

    Expected Response:
    {
        "session_id": "user_123",
        "message": "Session initialized successfully",
        "prospectuses": [
            {
                "prospectus_id": "uuid",
                "prospectus_name": "filename.pdf",
                "parse_status": "completed"
            }
        ]
    }
    """
    # Use user ID as session ID (or generate a unique session ID)
    session_id = f"user_{request.user.id}"

    # Initialize user session
    init_message = initialize_user_session(session_id)

    # Get user's prospectuses
    prospectuses = Prospectus.objects.filter(created_by=request.user).order_by('-upload_date')
    prospectus_data = ProspectusSerializer(prospectuses, many=True).data

    return Response({
        'session_id': session_id,
        'message': init_message,
        'prospectuses': prospectus_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_active_prospectus_view(request):
    """
    Set the active prospectus for the user's session.

    This should be called when the user selects a prospectus from the sidebar.

    Expected Request:
    {
        "prospectus_id": "uuid"
    }

    Expected Response:
    {
        "message": "Active prospectus updated",
        "prospectus_name": "filename.pdf"
    }
    """
    prospectus_id = request.data.get('prospectus_id')
    if not prospectus_id:
        return Response(
            {'error': 'prospectus_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    session_id = f"user_{request.user.id}"

    # Validate prospectus exists and user has access
    try:
        prospectus = Prospectus.objects.get(prospectus_id=prospectus_id)
        if prospectus.created_by != request.user:
            return Response(
                {'error': 'You do not have access to this prospectus'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Prospectus.DoesNotExist:
        return Response(
            {'error': 'Prospectus not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Update backend session
    if session_id in _SESSION_STORE:
        _SESSION_STORE[session_id]['active_prospectus_id'] = str(prospectus.prospectus_id)
        _SESSION_STORE[session_id]['active_prospectus_name'] = prospectus.prospectus_name
    else:
        # Initialize session if not exists
        _SESSION_STORE[session_id] = {
            'active_prospectus_id': str(prospectus.prospectus_id),
            'active_prospectus_name': prospectus.prospectus_name,
            'conversation_history': []
        }

    return Response({
        'message': 'Active prospectus updated',
        'prospectus_id': str(prospectus.prospectus_id),
        'prospectus_name': prospectus.prospectus_name
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_chat_message(request):
    """
    Send chat message and get agent response.

    The backend uses the session to determine which prospectus is active.
    User must have selected a prospectus via the sidebar first.

    Expected Request:
    {
        "message": "What is the deal structure?"
    }

    Expected Response:
    {
        "id": "msg_123",
        "role": "assistant",
        "content": "The deal structure is...",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    from agents.query_agent import run_agent, extract_response

    message = request.data.get('message')
    if not message:
        return Response(
            {'error': "message missing in the input"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Use user ID to get session
    session_id = f"user_{request.user.id}"

    # Run query agent (agent will use session to get active prospectus)
    try:
        result = run_agent(session_id=session_id, user_query=message)
        response_content = extract_response(result)

        response_message = {
            'id': str(uuid.uuid4()),
            'role': 'assistant',
            'content': response_content,
            'timestamp': datetime.now().isoformat()
        }

        return Response(response_message, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': f'Query agent error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
