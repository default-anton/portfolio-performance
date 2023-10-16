import locale


def currency(number):
    return locale.currency(number, grouping=True)
