"""Blueprint Flask, satu modul per area fitur."""
from . import auth, files, history, prediction, preprocess, settings, training, users

BLUEPRINTS = [m.bp for m in (auth, users, files, preprocess, training, prediction,
                             history, settings)]
