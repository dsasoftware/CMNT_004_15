# -*- coding: utf-8 -*-
from peewee import CharField, IntegerField
from app import app
from database import SyncModel


class Country(SyncModel):
    odoo_id = IntegerField(unique=True)
    name = CharField(max_length=150)
    code = CharField(max_length=5)

    MOD_NAME = 'country'

    def __unicode__(self):
        return self.name
