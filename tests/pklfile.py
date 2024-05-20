import pickle

cookies = [
    {"name": "IDE", "value": "AHWqTUmcpn4BcmzJkW2EHx9elirWAAW9rtBVu8A1xuFCB_E-rzKWP98N8vby-fjh_Uk", "domain": ".doubleclick.net", "path": "/", "expires": "2025-06-24T19:06:56.733Z", "secure": True, "httpOnly": True},
    {"name": "_ga", "value": "GA1.2.686318116.1716232017", "domain": ".x.com", "path": "/", "expires": "2025-06-24T19:06:56.833Z"},
    {"name": "_gid", "value": "GA1.2.1361101588.1716232017", "domain": ".x.com", "path": "/", "expires": "2024-05-21T19:06:56.000Z"},
    {"name": "ar_debug", "value": "1", "domain": ".www.google-analytics.com", "path": "/", "expires": "2024-06-18T21:06:43.677Z", "secure": True, "httpOnly": True},
    {"name": "auth_token", "value": "00269a603becfb9c8d4f39129cae94aff2fc60f1", "domain": ".x.com", "path": "/", "expires": "2025-05-20T19:06:53.610Z", "secure": True, "httpOnly": True},
    {"name": "ct0", "value": "c61778466049ebfa822c429eb1a698d933b665c08f41834f3955ac79ed4e5062e47216306ad59a465c097ad2419c925864d744313767903fe05ff1b56f52752f92308bd589b1e2232731d2627ef81ce4", "domain": ".x.com", "path": "/", "expires": "2025-06-24T19:06:53.701Z", "secure": True, "sameSite": "Lax"},
    {"name": "guest_id", "value": "v1%3A169098858918068369", "domain": ".x.com", "path": "/", "expires": "2025-05-20T19:06:53.610Z", "secure": True},
    {"name": "guest_id_ads", "value": "v1%3A169098858918068369", "domain": ".x.com", "path": "/", "expires": "2025-06-24T19:06:53.701Z", "secure": True},
    {"name": "guest_id_marketing", "value": "v1%3A169098858918068369", "domain": ".x.com", "path": "/", "expires": "2025-06-24T19:06:53.701Z", "secure": True},
    {"name": "lang", "value": "en", "domain": "x.com", "path": "/"},
    {"name": "muc_ads", "value": "157673d2-ecd8-415b-bb17-6937fefd5952", "domain": ".t.co", "path": "/", "expires": "2024-09-05T15:03:09.236Z", "secure": True},
    {"name": "personalization_id", "value": "\"v1_aBD0e/6kkJfNJ5WJUL3pJg==\"", "domain": ".x.com", "path": "/", "expires": "2025-06-24T19:06:53.701Z", "secure": True},
    {"name": "twid", "value": "u%3D16196634", "domain": ".x.com", "path": "/", "expires": "2025-05-20T19:07:08.183Z", "secure": True}
]

# Save the cookies to a pickle file
file_path = 'cookies.pkl'
with open(file_path, 'wb') as file:
    pickle.dump(cookies, file)

print(f"Cookies have been successfully saved to {file_path}.")