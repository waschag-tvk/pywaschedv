# Specifications

* existing data has to be imported
* framework will be Django (Python)
* connection to Netz-AG (vereinskasse)

## Wasch-AG web

* machine booking info
  * dates, user etc.
  * booking history
  * status history
  * place (e.g. AG-Raum)
* login/out → LDAP
* confirmation of new users
  * all login info with Netz-AG
* hardware interface
* price per wasch slot
  * other parameters (free wash count, late timeout etc.)
* tidy up homescreen (those repetitive user messages)
* waschparam: name (short), value, label

## User
* interface for managing users (LDAP?)
  * additionally manage confirmed status (user instructed about washing equipment usage)
  * IP restriction not necessarily per user but at least to the tower
  * status --> can be chosen with understandable labels
* functions: activate, change status, block, unblock 

## Appointment

* time, user, machine, used, refunded, transactions
* pricing → functions instead of table (more flexible)
* functions: book, cancel, refund, use

## Waschente

* use python too?

## Money

* credit to Netz-AG account
* separate account for cash (like Wasch-AG-Kontostand)
* money between Netz-AG ↔ Wasch-AG?
* no bonus
