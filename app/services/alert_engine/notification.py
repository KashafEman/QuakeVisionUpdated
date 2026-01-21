from firebase_admin import messaging

def send_push_notification(message: str, title: str = "QuakeVision Alert") -> None:
    """
    Sends a push notification to all subscribed users via Firebase Cloud Messaging (FCM).
    """
    # TODO: Replace with actual list of FCM tokens from Firestore
    user_tokens = get_all_user_tokens()  

    if not user_tokens:
        print("No user tokens found. Skipping notification.")
        return

    for token in user_tokens:
        notification = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message
            ),
            token=token
        )

        try:
            response = messaging.send(notification)
            print(f"Notification sent successfully: {response}")
        except Exception as e:
            print(f"Failed to send notification to {token}: {e}")

def get_all_user_tokens():
    """
    Fetch all user FCM tokens from Firestore.
    Modify this based on your users collection structure.
    """
    from app.init_firebase import db

    tokens = []
    users_ref = db.collection("users").stream()
    for doc in users_ref:
        data = doc.to_dict()
        token = data.get("fcm_token")
        if token:
            tokens.append(token)
    return tokens
