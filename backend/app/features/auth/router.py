"""Auth endpoints. Cookies are an HTTP concern, so they are handled here; logic lives in AuthService."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import SessionDep, TicketsDep, auth_rate_limit, require_trusted_origin
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError, RateLimitedError, error_body
from app.features.auth.dependencies import CurrentUser
from app.features.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, WsTicketResponse
from app.features.auth.service import AuthService, IssuedSession
from app.features.users.schemas import UserMe

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/api/v1/auth"


def get_auth_service(session: SessionDep, request: Request) -> AuthService:
    return AuthService(session, get_settings(), request.app.state.login_limiter)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME, token, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, httponly=True,
        secure=settings.COOKIE_SECURE, samesite="strict", path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, secure=s.COOKIE_SECURE,
                           httponly=True, samesite="strict")


def _token_response(issued: IssuedSession, response: Response) -> TokenResponse:
    set_refresh_cookie(response, issued.refresh_token, get_settings())
    return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in,
                         user=UserMe.model_validate(issued.user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(auth_rate_limit)])
async def register(body: RegisterRequest, auth: AuthServiceDep, response: Response) -> TokenResponse:
    return _token_response(await auth.register(body), response)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(body: LoginRequest, auth: AuthServiceDep, response: Response) -> TokenResponse:
    return _token_response(await auth.login(body.login, body.password), response)


@router.post("/refresh", response_model=TokenResponse,
             dependencies=[Depends(auth_rate_limit), Depends(require_trusted_origin)])
async def refresh(request: Request, auth: AuthServiceDep, response: Response) -> TokenResponse | JSONResponse:
    try:
        issued = await auth.refresh(request.cookies.get(get_settings().REFRESH_COOKIE_NAME))
    except AuthError as exc:
        # Build the 401 here so the stale cookie is actually cleared (raising would drop `response`).
        failure = JSONResponse(error_body(exc.code, exc.message), status_code=401,
                               headers={"WWW-Authenticate": "Bearer"})
        clear_refresh_cookie(failure)
        return failure
    return _token_response(issued, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def logout(request: Request, auth: AuthServiceDep) -> Response:
    await auth.logout(request.cookies.get(get_settings().REFRESH_COOKIE_NAME))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserMe)
async def me(user: CurrentUser) -> UserMe:
    return UserMe.model_validate(user)


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def ws_ticket(user: CurrentUser, tickets: TicketsDep, request: Request) -> WsTicketResponse:
    """Short-lived single-use ticket for authenticating the WebSocket (no JWT in URLs)."""
    if not request.app.state.ticket_limiter.allow(str(user.id)):
        raise RateLimitedError("Too many connection attempts, slow down")
    return WsTicketResponse(ticket=tickets.issue(user.id), expires_in=tickets.ttl)
