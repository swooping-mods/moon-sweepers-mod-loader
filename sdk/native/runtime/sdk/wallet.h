#ifndef MOONLAB_SDK_WALLET_H
#define MOONLAB_SDK_WALLET_H
/* The adapter owns authority, player rooting, prices and its transaction ledger.
 * All callbacks are synchronous on its game thread. Successful adjustment
 * requires exact balance confirmation; uncertain debits must latch the domain.
 * Compensation is best effort, not atomicity across wallet and sidecar files. */
typedef struct {
  int (*balance)(void *context, long long *amount);
  int (*adjust)(void *context, int delta);
} MoonWallet;
enum {
  MW_PAID = 1,
  MW_UNAVAILABLE = 0,
  MW_INSUFFICIENT = -1,
  MW_DEBIT_REFUSED = -2,
  MW_DEBIT_UNCONFIRMED = -3,
  MW_SAVE_REFUNDED = -4,
  MW_REFUND_UNCONFIRMED = -5
};
static inline int mw_debit(const MoonWallet *wallet, void *context, int cost,
                          long long *previous) {
  long long before = 0, after = 0;
  if (!wallet || !wallet->balance || !wallet->adjust || cost < 0)
    return MW_UNAVAILABLE;
  if (!wallet->balance(context, &before) || before < 0)
    return MW_UNAVAILABLE;
  if (before < cost) return MW_INSUFFICIENT;
  if (previous) *previous = before;
  if (!cost) return MW_PAID;
  if (!wallet->adjust(context, -cost)) return MW_DEBIT_REFUSED;
  if (!wallet->balance(context, &after) || after != before - cost)
    return MW_DEBIT_UNCONFIRMED;
  return MW_PAID;
}
/* commit must revert its staged in-memory ownership on failure. Domain state
 * must remain untouched on debit failures. Never retry an uncertain payment. */
static inline int mw_purchase(const MoonWallet *wallet, void *context, int cost,
                              int (*commit)(void *)) {
  long long before = 0, after = 0;
  if (!commit) return MW_UNAVAILABLE;
  int result = mw_debit(wallet, context, cost, &before);
  if (result != MW_PAID) return result;
  if (commit(context)) return MW_PAID;
  if ((!cost || wallet->adjust(context, cost)) &&
      wallet->balance(context, &after) && after == before)
    return MW_SAVE_REFUNDED;
  return MW_REFUND_UNCONFIRMED;
}
#endif
