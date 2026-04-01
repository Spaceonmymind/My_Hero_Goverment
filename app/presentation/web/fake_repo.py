# app/presentation/web/fake_repo.py

TASKS = {
    1: {
        "id": 1,
        "title": "Участие в акции",
        "description": "Прими участие в школьной акции и загрузи фото",
        "category": "События",
        "points": 20,
        "type": "media",
    },
    2: {
        "id": 2,
        "title": "Посещение кружка",
        "description": "Посети любой кружок и опиши, чем занимались",
        "category": "Образование",
        "points": 15,
        "type": "text",
    },
    3: {
        "id": 3,
        "title": "Волонтёрство",
        "description": "Участие в волонтёрской активности",
        "category": "Соц. активность",
        "points": 50,
        "type": "media",
    },
}

SUBMISSIONS = []  # {id, task_id, user_email, status, comment}
BALANCES = {"student@demo": 120}
