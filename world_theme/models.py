from CTFd.models import db

class ChallengeCountry(db.Model):
    __tablename__ = "challenge_countries"
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    country_iso = db.Column(db.String(2), nullable=False, index=True)
    bonus_first = db.Column(db.Integer, default=0)
    bonus_second = db.Column(db.Integer, default=0)
    bonus_third = db.Column(db.Integer, default=0)
    bonus_fourth = db.Column(db.Integer, default=0)
    bonus_fifth = db.Column(db.Integer, default=0)

    def __init__(self, challenge_id, country_iso, bonus_first=0, bonus_second=0, bonus_third=0, bonus_fourth=0, bonus_fifth=0):
        self.challenge_id = challenge_id
        self.country_iso = country_iso.upper()
        self.bonus_first = bonus_first or 0
        self.bonus_second = bonus_second or 0
        self.bonus_third = bonus_third or 0
        self.bonus_fourth = bonus_fourth or 0
        self.bonus_fifth = bonus_fifth or 0

    @property
    def bonus_levels(self):
        return [
            self.bonus_first or 0,
            self.bonus_second or 0,
            self.bonus_third or 0,
            self.bonus_fourth or 0,
            self.bonus_fifth or 0,
        ]
