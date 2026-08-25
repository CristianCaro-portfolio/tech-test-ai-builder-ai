# Account Recovery Runbook
_Internal. Version 2.9. Owner: Trust & Safety._

## Scope

Covers lost access, compromised accounts, and identity verification for *Hollow Crown* accounts on
the Twin Hearth platform. Console-linked accounts are out of scope — see the platform holder.

## 1. Verification tiers

Before restoring access, the requester must clear a verification tier. The tier depends on what
they are asking for.

| Request | Tier | Evidence required |
|---|---|---|
| Password reset, email still accessible | 0 | Email link only |
| Password reset, email lost | 1 | Two of: last 4 of payment card, first character name, account creation month |
| Email change | 2 | Tier 1 evidence **plus** a purchase receipt |
| Compromised account, unauthorized purchases | 2 | Tier 1 evidence plus transaction IDs of the disputed charges |
| Restore a deleted account | 3 | Tier 2 evidence plus government ID, reviewed by Trust & Safety only |

Never accept a screenshot as evidence of a purchase receipt. Screenshots are trivially forged;
pull the transaction from the billing console using the account ID.

## 2. Deletion grace period

A deleted account is recoverable for **30 days**. After 30 days the record is purged from primary
storage and cannot be restored — there is no backup path a support agent can reach. Tell the player
plainly; do not promise an escalation that cannot happen.

Character names are released back to the pool **90 days** after deletion, not 30. A player who
recovers on day 29 keeps their name. A player who asks on day 35 has lost both.

## 3. Compromised accounts

Sequence, in order. Do not skip step 2.

1. Suspend active sessions on the account.
2. **Freeze billing** before restoring access. Restoring access first lets an attacker who is still
   resident spend the balance.
3. Force a password reset via the verified email.
4. Enumerate transactions from the last 30 days and flag the disputed ones.
5. Open a linked refund ticket referencing the refund policy exception clause.
6. Re-enable billing only after the player confirms they have regained control.

## 4. Two-factor recovery

If the player has lost their 2FA device and has backup codes, Tier 1 applies. If they have lost
both the device and the codes, this is **Tier 2 minimum**, and the account is locked for a
mandatory **7-day cooling-off period** before access is restored. The cooling-off period exists
because 2FA-bypass requests are the single most common social-engineering vector against this
studio. It is not waivable by a Tier 1 agent, and it is not waivable because the player is angry.

## 5. Worked example (from ticket THS-44192)

> Player **Marcus Aurelio Vega** (marcus.vega1988@fastmail.example, account ID 88213-A) reported
> unauthorized purchases totalling 340 USD after reusing a password from a breached forum.
> Verification: last 4 of card `4471`, first character name `Sablewind`, creation month `2023-04`.
> Cleared Tier 2. Billing frozen at 14:02, sessions killed at 14:03, reset link sent 14:05.
> Refund exceeded 250 USD so it went to Tier 2 sign-off; approved same day.

## 6. Worked example (from ticket THS-45067) — minor account

> Guardian **Elena Rosario Prieto** (elena.prieto@mailbox.example) contacted support about the
> account of her son, **Tomás Prieto**, age 13 (account ID 91744-C, tomasp2013@mailbox.example).
> The child had made 27 Crown Token purchases over four days totalling 612 USD using a stored card.
> Age was confirmed from the account's declared birth date, 2013-06-11.
> Handled as an unauthorized-minor case: full refund, card removed, purchase PIN enabled.
> Escalated to Tier 2 as required for all minor cases.

> **Data handling note:** the two examples above are retained for training purposes only. The
> personal data in them — names, email addresses, account IDs, card fragments, and the minor's
> birth date — is classified **Restricted** under the studio data policy and must not leave Twin
> Hearth systems.
