from django.utils.translation import ugettext_lazy as _

# Folder types
NORMAL = 0
INBOX = 1
OUTBOX = 2
DRAFTS = 3
QUEUE = 4
TRASH = 5
OTHER = 6  # For proprietary stuff like Gmail's Starred/All mail
FOLDER_TYPES = (
    (NORMAL, _('Normal')),
    (INBOX, _('Inbox')),
    (OUTBOX, _('Outbox')),
    (DRAFTS, _('Drafts')),
    (QUEUE, _('Queue')),
    (TRASH, _('Trash')),
    (OTHER, _('Other')),
)
