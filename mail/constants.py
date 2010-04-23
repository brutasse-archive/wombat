from django.utils.translation import ugettext_lazy as _

# Folder types
NORMAL = 100
INBOX = 10
OUTBOX = 20
DRAFTS = 30
QUEUE = 40
TRASH = 50
SPAM = 60
OTHER = 70  # For proprietary stuff like Gmail's Starred/All mail
FOLDER_TYPES = (
    (NORMAL, _('Normal')),
    (INBOX, _('Inbox')),
    (OUTBOX, _('Outbox')),
    (DRAFTS, _('Drafts')),
    (QUEUE, _('Queue')),
    (TRASH, _('Trash')),
    (SPAM, _('Spam')),
    (OTHER, _('Other')),
)
