from peewee import *

database = MySQLDatabase('anonwaschag', **{'password': 'waschagpassword', 'user': 'waschag'})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class Config(BaseModel):
    wert = FloatField()
    zweck = TextField()

    class Meta:
        db_table = 'config'
        primary_key = False

class DokuEng(BaseModel):
    abschnitt = IntegerField()
    inhalt = TextField()
    paragraph = IntegerField()
    satz = IntegerField()
    titel = TextField()

    class Meta:
        db_table = 'doku_eng'
        primary_key = False

class DokuGer(BaseModel):
    abschnitt = IntegerField()
    inhalt = TextField()
    paragraph = IntegerField()
    satz = IntegerField()
    titel = TextField()

    class Meta:
        db_table = 'doku_ger'
        primary_key = False

class Finanzlog(BaseModel):
    aktion = FloatField()
    bemerkung = TextField()
    bestand = FloatField()
    bonus = IntegerField()
    datum = DateTimeField(null=True)
    user = IntegerField()

    class Meta:
        db_table = 'finanzlog'
        primary_key = False

class Notify(BaseModel):
    datum = DateField(null=True)
    id = IntegerField(null=True)
    ziel = TextField(null=True)

    class Meta:
        db_table = 'notify'
        primary_key = False

class Preise(BaseModel):
    preis = FloatField()
    tag = IntegerField()
    zeit = IntegerField()

    class Meta:
        db_table = 'preise'
        primary_key = False

class Termine(BaseModel):
    bonus = IntegerField(null=True)
    datum = DateField()
    maschine = IntegerField()
    user = IntegerField()
    wochentag = IntegerField()
    zeit = IntegerField()

    class Meta:
        db_table = 'termine'
        primary_key = False

class Users(BaseModel):
    bemerkung = TextField()
    gesperrt = IntegerField()
    gotfreimarken = IntegerField()
    ip = TextField()
    lastlogin = DateField()
    login = TextField()
    message = TextField()
    nachname = TextField()
    name = TextField()
    pw = TextField()
    status = IntegerField()
    termine = IntegerField()
    von = IntegerField()
    zimmer = IntegerField()

    class Meta:
        db_table = 'users'

class Waschagtransaktionen(BaseModel):
    aktion = FloatField()
    bemerkung = TextField()
    bestand = FloatField()
    datum = DateTimeField(null=True)
    user = IntegerField()

    class Meta:
        db_table = 'waschagtransaktionen'
        primary_key = False

class Waschmaschinen(BaseModel):
    bemerkung = TextField(null=True)
    id = IntegerField()
    status = IntegerField()
    von = IntegerField()

    class Meta:
        db_table = 'waschmaschinen'
        primary_key = False

