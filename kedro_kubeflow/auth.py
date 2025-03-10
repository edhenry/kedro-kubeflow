import html
import logging
import os
import re
from urllib.parse import urlsplit, urlunsplit

import requests

IAP_CLIENT_ID = "IAP_CLIENT_ID"
DEX_USERNAME = "DEX_USERNAME"
DEX_PASSWORD = "DEX_PASSWORD"


class AuthHandler(object):
    log = logging.getLogger(__name__)

    def obtain_id_token(self):
        from google.auth.exceptions import DefaultCredentialsError
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        client_id = os.environ.get(IAP_CLIENT_ID, None)

        jwt_token = None

        if not client_id:
            self.log.debug(
                "No IAP_CLIENT_ID provided, skipping custom IAP authentication"
            )
            return jwt_token

        try:
            self.log.debug("Attempt to get IAP token for %s." + client_id)
            jwt_token = id_token.fetch_id_token(Request(), client_id)
            self.log.info("Obtained JWT token for IAP proxy authentication.")
        except DefaultCredentialsError as ex:
            self.log.warning(
                str(ex)
                + (
                    " Note that this authentication method does not work with default"
                    " credentials obtained via 'gcloud auth application-default login'"
                    " command. Refer to documentation on how to configure service account"
                    " locally"
                    " (https://cloud.google.com/docs/authentication/production#manually)"
                )
            )
        except Exception as e:
            self.log.error("Failed to obtain IAP access token. " + str(e))
        finally:
            return jwt_token

    # DEX supports Resource Owner Password Credentials Grant only for LDAP connectors.
    # And it doesn't work for Open ID Connect, e.g. Google (Moreover,
    # Google doesn't support such a flow at all).
    # Here is a hacky workaround - we imitate a web browser to navigate to the login page and
    # proceed with 'Log in with Email'. It does work,
    # but it is prone to errors if anything substantial changes in the way DEX handles login screens.
    def obtain_dex_authservice_session(self, kfp_api):
        if DEX_USERNAME not in os.environ or DEX_PASSWORD not in os.environ:
            self.log.debug("Skipping DEX authentication due to missing env variables")
            return None

        s = requests.Session()
        kfp_url_parts = urlsplit(kfp_api)

        def extract_url(regexp, response: str):
            form_url = re.search(regexp, response)

            if form_url:
                return urlunsplit(
                    [
                        kfp_url_parts.scheme,
                        kfp_url_parts.netloc,
                        html.unescape(form_url.group(0)),
                        None,
                        None,
                    ]
                )
            return None

        r = s.get(kfp_api)

        login_url = extract_url('/dex/auth/local/login\\?back=[^"]*', r.text)

        if not login_url:
            login_form_url = extract_url('/dex/auth/local/login\\?back=[^"]*', r.text)

            r = s.get(login_form_url)

            login_url = extract_url('/dex/auth/local/login\\?back=[^"]*', r.text)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "login": os.environ[DEX_USERNAME],
            "password": os.environ[DEX_PASSWORD],
        }

        s.post(login_url, headers=headers, data=data)
        return s.cookies.get_dict()["authservice_session"]
