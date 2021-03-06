from enum import Enum
import walletscan
import codecs
import time
from datetime import datetime


class TransferType(Enum):
    Deposit = 'Einzahlung'
    Revenues = 'Einnahme'
    Mining = 'Mining'
    GiftIn = 'Geschenk'
    Withdrawal = 'Auszahlung'
    Expense = 'Ausgabe'
    Donation = 'Spende'
    GiftOut = 'Schenkung'
    Stolen = 'Gestohlen'
    Loss = 'Verlust'


class TronTransferExporter(object):
    """Exporter Class for Tron transfers."""

    def __init__(self, wallet_address):
        self.wallet_address = wallet_address
        self.assignments = []
        self.group_filters = []
        self.currency_filters = []
        self.currency_aliases = {}

    def add_assign(self, transfer_type: TransferType, from_address=None, to_address=None):
        """
        Adds transfer assignments. Transfers are assigned to specific transfer types based on the assignment. 
        Without assignment, transfers will be declared as deposits or withdrawals.

        Arguments:
            transfer_type {CTTransferType} -- Type which will be assigned to the transfers.

        Keyword Arguments:
            from_address {str} -- Affected transfers with this sender address. (default: {None})
            to_address {str} -- Affected transfers with this destination address. (default: {None})
        """

        if from_address is None and to_address is None:
            print('Either sender address or destination address must be set.')
            return

        self.assignments.append({'transfer_type': transfer_type,
                                 'from_address': from_address, 'to_address': to_address})

    def add_currency_filter(self, currency: str):
        """
        Adds currency filters. Only transfers with added currencies will be considered. 
        If no filter is added, all transfers will be considered.

        Arguments:
            currency {str} -- Name of the currency
        """

        self.currency_filters.append(currency)

    def add_currency_alias(self, currency: str, alias: str):
        """
        Adds aliases for currency names. In the export, the names will be replaced by the aliases.

        Arguments:
            currency {str} -- Name of the currency
            alias {str} -- Alias of the currency
        """

        self.currency_aliases[currency] = alias

    def add_group_filter(self, currency: str, from_address=None, to_address=None):
        """
        Adds transfers from specific senders or receivers to a group. Grouped transfers are merged into one transfer when exported.

        Keyword Arguments:
            currency {str} -- Currencies which will be grouped together.
            from_address {str} -- Affected transfers with this sender address. (default: {None})
            to_address {str} -- Affected transfers with this destination address. (default: {None})
        """

        if from_address is None and to_address is None:
            print('Either sender address or destination address must be set.')
            return

        self.group_filters.append(
            {'currency': currency, 'from_address': from_address, 'to_address': to_address})

    def _group_transfers(self, transfers: [walletscan.TronTransfer]):
        """Groups the transfers for merging.
        
        Arguments:
            transfers {[TronTransfer]} -- Transfers which will be grouped.
        
        Returns:
            dict -- Grouped transfers.
        """
        if not self.group_filters:
            return {}, transfers

        sorted_tr = sorted(transfers, key=lambda x: x.timestamp)

        grouped_tr = {}
        ungrouped_tr = []
        new_group_currenys = []
        for t in sorted_tr:
            for g_filter in self.group_filters:
                is_grouped = False

                # deposit
                if g_filter['from_address'] is not None and g_filter['from_address'] == t.from_address:
                    # Add token as a new category, if the category doesn't exist yet
                    if t.token_name not in grouped_tr:
                        grouped_tr[t.token_name] = {'count': 0, 'groups': []}

                    # Add new Group, if the token has nos group yet
                    if grouped_tr[t.token_name]['count'] == 0:
                        grouped_tr[t.token_name]['groups'].append({'is_outgoing': False,
                                                                   'address': t.from_address,
                                                                   'transfers': []})
                        grouped_tr[t.token_name]['count'] = 1

                    # Current group index
                    group_index = grouped_tr[t.token_name]['count'] - 1

                    # If the current transfer does not fit into the group, new group will be created
                    if grouped_tr[t.token_name]['groups'][group_index]['is_outgoing'] or \
                       grouped_tr[t.token_name]['groups'][group_index]['address'] != t.from_address or \
                       t.token_name in new_group_currenys:

                        # Add new group
                        grouped_tr[t.token_name]['groups'].append({'is_outgoing': False,
                                                                   'address': t.from_address,
                                                                   'transfers': []})

                        grouped_tr[t.token_name]['count'] += 1
                        group_index = grouped_tr[t.token_name]['count'] - 1
                        if t.token_name in new_group_currenys:
                            new_group_currenys.remove(t.token_name)

                    # Add transfer to group
                    grouped_tr[t.token_name]['groups'][group_index]['transfers'].append(
                        t)
                    is_grouped = True
                    break

                # withdrawal
                elif g_filter['to_address'] is not None and g_filter['to_address'] == t.to_address:
                     # Add token as a new category, if the category doesn't exist yet
                    if t.token_name not in grouped_tr:
                        grouped_tr[t.token_name] = {'count': 0, 'groups': []}

                    # Add new Group, if the token has nos group yet
                    if grouped_tr[t.token_name]['count'] == 0:
                        grouped_tr[t.token_name]['groups'].append({'is_outgoing': True,
                                                                   'address': t.to_address,
                                                                   'transfers': []})
                        grouped_tr[t.token_name]['count'] = 1

                    # Current group index
                    group_index = grouped_tr[t.token_name]['count'] - 1

                    # If the current transfer does not fit into the group, new group will be created
                    if grouped_tr[t.token_name]['groups'][group_index]['is_outgoing'] or \
                       grouped_tr[t.token_name]['groups'][group_index]['address'] != t.to_address or \
                       t.token_name in new_group_currenys:

                        # Add new group
                        grouped_tr[t.token_name]['groups'].append({'is_outgoing': True,
                                                                   'address': t.to_address,
                                                                   'transfers': []})

                        grouped_tr[t.token_name]['count'] += 1
                        group_index = grouped_tr[t.token_name]['count'] - 1
                        if t.token_name in new_group_currenys:
                            new_group_currenys.remove(t.token_name)

                    # Add transfer to group
                    grouped_tr[t.token_name]['groups'][group_index]['transfers'].append(
                        t)
                    is_grouped = True
                    break

            if not is_grouped:
                if t.token_name in grouped_tr and t.token_name not in new_group_currenys:
                    new_group_currenys.append(t.token_name)

                # Add transfer to the not grouped
                ungrouped_tr.append(t)

        groups = []
        for _, value in grouped_tr.items():
            for g_filter in value['groups']:
                groups.append(g_filter['transfers'])

        return groups, ungrouped_tr

    def _merge_transfers(self, transfers: [walletscan.TronTransfer]):
        """
        Merges grouped transfers into one transfer. Transfers with different currencies will be not merged. 
        Groups can be created with the "add_group()" function.


        Arguments:
            transfers {[tronparser.TronTransfer]} -- List of TronTransfer
        """

        if not self.group_filters:
            return transfers

        groups, trs = self._group_transfers(transfers)

        for g in groups:
            transfer = walletscan.TronTransfer()
            transfer.amount = 0
            transfer.from_address = g[0].from_address
            transfer.to_address = g[0].to_address
            transfer.token_name = g[0].token_name
            transfer.confirmed = True

            for t in g:
                transfer.timestamp = t.timestamp
                transfer.amount += t.amount
                transfer.confirmed &= g[0].confirmed

            # ToDo localisation
            transfer.comment = 'Grouped ' + \
                g[0].get_date(timezone='Europe/Berlin') + ' - ' + transfer.get_date(timezone='Europe/Berlin')
            trs.append(transfer)

        trs.sort(key=lambda x: x.timestamp)

        return trs

    def export_csv(self, filename: str, start_date: str = None, end_date: str = None):
        raise NotImplementedError()


class CoinTrackingExporter(TronTransferExporter):
    """Exporter class of Tron transfers to a readable file for CoinTracking.info."""

    def __init__(self, wallet_address, wallet_name=None):
        super().__init__(wallet_address)
        self.wallet_name = wallet_name

    def export_csv(self, filename: str, start_date: str = None, end_date: str = None):
        """
        Fetches the transfers from the wallet and exports them to a csv file.

        Arguments:
            filename {str} -- Destination file.
            start_date {str} -- Exports all transfers from including this date. Format: "yyyy-mm-dd hh:mm:ss"
            end_date {str} -- Exports all transfers up to and including this date. Format: "yyyy-mm-dd hh:mm:ss"
        """

        ts_start = None
        if start_date is not None:
            ts_start = time.mktime(datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S').timetuple())
            ts_start = int(ts_start * 1000)

        ts_end = None
        if end_date is not None:
            ts_end = time.mktime(datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').timetuple())
            ts_end = int(ts_end * 1000)

        print("Fetching transfers from tronscan.org API ...")
        scanner = walletscan.TronScan(self.wallet_address)
        transfers = scanner.get_transfers(tokens=self.currency_filters, ts_start=ts_start, ts_end=ts_end)
        ptr = walletscan.TronTransfer.parse_transfers(transfers)
        print("Fetching success.")

        if self.group_filters:
            print("Merging grouped transfers ...")
            ptr = self._merge_transfers(ptr)
            print("Merging success.")

        print("Writing CSV for CoinTracking.info ...")

        with codecs.open(filename, 'w', 'utf-8') as csvf:

            # ToDo: Switchable language
            csvf.write(r'"Typ","Kauf","Cur.","Verkauf","Cur.","Gebühr","Cur.","Börse","Gruppe","Kommentar","Datum"')

            for tr in ptr:
                line = '\n'
                has_assign = False
                tr_type = TransferType.Deposit

                # Type
                for assign in self.assignments:
                    if tr.from_address == assign['from_address'] or tr.to_address == assign['to_address']:
                        tr_type = assign['transfer_type']
                        has_assign = True
                        break

                if not has_assign:
                    if tr.to_address == self.wallet_address:
                        tr_type = TransferType.Deposit

                    elif tr.from_address == self.wallet_address:
                        tr_type = TransferType.Withdrawal

                    else:
                        print('Something went wrong.')
                        exit()

                line += '\"' + tr_type.value + '\",'

                amount = 0
                cur = ''

                if tr.token_name == '_':
                    amount = tr.amount / 1000000
                    cur = 'TRX'
                else:
                    token_info = walletscan.TronScan.get_token_info(tr.token_name)
                    precision = token_info['data'][0]['precision']

                    amount = tr.amount / (10**precision)

                    if tr.token_name in self.currency_aliases:
                        cur = self.currency_aliases[tr.token_name]
                    else:
                        cur = tr.token_name

                if tr_type.value == TransferType.Deposit.value or \
                   tr_type.value == TransferType.Revenues.value or \
                   tr_type.value == TransferType.Mining.value or \
                   tr_type.value == TransferType.GiftIn.value:

                    # Buy
                    line += '\"' + str(amount) + '\",\"' + cur + '\",'

                    # Sell
                    line += r'"","",'

                else:
                    # Buy
                    line += r'"","",'

                    # Sell
                    line += '\"' + str(amount) + '\",\"' + cur + '\",'

                # ToDo: Fee
                line += r'"","",'

                # Exchange
                line += '\"' + ('' if self.wallet_name is None else self.wallet_name) + '\",'

                # Group
                line += r'"",'

                # Comment
                line += '\"' + tr.comment + '\",'

                # Date
                line += '\"' + tr.get_date()

                csvf.write(line)

        print('Writing CSV finished.')
