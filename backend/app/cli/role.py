"""Operator-only command; never exposes an endpoint for self-assignment of roles."""

import argparse

from firebase_admin import auth

from app.core.config import Settings
from app.core.firebase import FirebaseRuntime
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set analyst/admin custom claims on an existing user"
    )
    parser.add_argument("uid")
    parser.add_argument("role", choices=["analyst", "admin"])
    parser.add_argument("--project-confirm", required=True)
    parser.add_argument("--marketlens", action="store_true")
    args = parser.parse_args()
    runtime = (
        marketlens_runtime(MarketLensSettings()) if args.marketlens else FirebaseRuntime(Settings())
    )
    if args.project_confirm != runtime.settings.firebase_project_id:
        parser.error("Project confirmation does not match FIREBASE_PROJECT_ID")
    try:
        app = runtime.app()
        user = auth.get_user(args.uid, app=app)
        claims = {**(user.custom_claims or {}), "role": args.role}
        auth.set_custom_user_claims(user.uid, claims, app=app)
        auth.revoke_refresh_tokens(user.uid, app=app)
        print("Role updated. The user must sign in again.")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
