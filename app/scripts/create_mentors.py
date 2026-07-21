from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

from app.infra.db import Base, SessionLocal, engine
from app.infra.models import MentorProfile, User
from app.infra.security import hash_password

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
Base.metadata.create_all(bind=engine)


MENTORS = [
    ("Мугинова Наталья Сергеевна", "nsmuginova@pervye.ru", "MuginNat"),
    ("Коробейникова Екатерина Викторовна", "evkorobeinikova@pervye.ru", "KorobEka"),
    ("Литвинов Михаил Александрович", "MALitvinov@pervye.ru", "LitviMih"),
    ("Титова Анастасия Леонидовна", "altitova@pervye.ru", "TitovAna"),
    ("Каргаполова Мария Вячеславовна", "mvkargapolova@pervye.ru", "KargaMar"),
    ("Деулин Сергей Викторович", "svdeulin@pervye.ru", "DeuliSer"),
    ("Данчина Екатерина Сергеевна", "EDanchina@pervye.ru", "DanchEka"),
    ("Пономарева Ирина Ивановна", "iiponomareva@pervye.ru", "PonomIri"),
    ("Прасолова Эльвира Николаевна", "enprasolova@pervye.ru", "PrasoElv"),
    ("Верещагина Екатерина Игоревна", "eivereshchagina@pervye.ru", "VeresEka"),
    ("Токушева Людмила Витальевна", "lvtokusheva@pervye.ru", "TokusLyu"),
    ("Бондаренко Любовь Юрьевна", "lbondarenko@pervye.ru", "BondaLyu"),
    ("Пожидаева Екатерина Григорьевна", "egpozhidaeva@pervye.ru", "PozhiEka"),
    ("Николаева Галина Андреевна", "ganikolaeva@pervye.ru", "NikolGal"),
    ("Удинцева Алла Владимировна", "avudintseva@pervye.ru", "UdintAll"),
    ("Блинова Ольга Сергеевна", "osblinova@pervye.ru", "BlinoOlg"),
    ("Гильманова Валерия Рашидовна", "vrgilmanova@pervye.ru", "GilmaVal"),
    ("Мандыргина Наталья Юрьевна", "nyumandrygina@pervye.ru", "MandrNat"),
    ("Кочнева Лариса Анатольевна", "LKochneva@pervye.ru", "KochnLar"),
    ("Котлова Юлия Сергеевна", "yuskotlova@pervye.ru", "KotloYul"),
    ("Бухарова Наталья Алексеевна", "nabukharova@pervye.ru", "BukhaNat"),
    ("Левина Любовь Евгеньевна", "lelevina@pervye.ru", "LevinLyu"),
    ("Кучина Марина Евгеньевна", "MEKuchina@pervye.ru", "KuchiMar"),
    ("Немчинов Олег Сергеевич", "osnemchinov@pervye.ru", "NemchOle"),
    ("Жмыхова Ольга Владимировна", "ovzhmykhova@pervye.ru", "ZhmykOlg"),
    ("Сан-Чун Ирина Николаевна", "insan-chun@pervye.ru", "SanChIri"),
    ("Григорьева Надежда Александровна", "nagrigoreva@pervye.ru", "GrigoNad"),
    ("Кривощёкова Юлия Владимировна", "yuvkrivoshchekova@pervye.ru", "KrivoYul"),
    ("Кайгородова Оксана Михайловна", "OMKaigorodova@pervye.ru", "KaigoOks"),
    ("Хохрякова Валентина Эдуардовна", "ValEKhokhryakova@pervye.ru", "KhokhVal"),
    ("Игнатьева Юлия Александровна", "yuaignateva@pervye.ru", "IgnatYul"),
    ("Романова Мария Александровна", "mararomanova@pervye.ru", "RomanMar"),
    ("Потребалова Наталья Андреевна", "napotrepalova@pervye.ru", "PotreNat"),
    ("Колчеданцева Мария Александровна", "kolch_84@mail.ru", "KolchMar"),
]


def main():
    created_count = 0
    updated_count = 0

    with SessionLocal() as db:
        for full_name, email, password in MENTORS:
            normalized_email = email.strip().lower()
            user = db.scalar(select(User).where(User.email == normalized_email))

            if not user:
                user = User(
                    email=normalized_email,
                    password_hash=hash_password(password),
                    role="mentor",
                )
                db.add(user)
                db.flush()
                created_count += 1
            else:
                if user.role != "mentor":
                    user.role = "mentor"
                    updated_count += 1

            profile = db.scalar(
                select(MentorProfile).where(MentorProfile.user_id == user.id)
            )
            if not profile:
                db.add(MentorProfile(user_id=user.id, full_name=full_name))
            elif profile.full_name != full_name:
                profile.full_name = full_name

        db.commit()

    print(f"Created mentors: {created_count}")
    print(f"Updated existing users: {updated_count}")
    print()
    print("Credentials:")
    for full_name, email, password in MENTORS:
        print(f"{full_name}; {email.strip().lower()}; {password}")


if __name__ == "__main__":
    main()
