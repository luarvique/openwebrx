# Various reverse-engineered versions of the allocation algorithms
# used by different countries to allocate 24-bit ICAO addresses based
# on the aircraft registration.
#
# These were worked out by looking at the allocation patterns and
# working backwards to an algorithm that generates that pattern,
# spot-checking aircraft to see if it worked.
# YMMV.
class IcaoRegistration(object):

    @staticmethod
    def find(icao: int):
        result = IcaoRegistration.n_reg(icao)
        if result is not None:
            return result
        result = IcaoRegistration.ja_reg(icao)
        if result is not None:
            return result
        result = IcaoRegistration.hl_reg(icao)
        if result is not None:
            return result
        result = NumericMapping.find(icao)
        if result is not None:
            return result
        result = StrideMapping.find(icao)
        if result is not None:
            return result
        return None;

    # South Korea (HLxxxx)
    @staticmethod
    def hl_reg(icao: int):
        if 0x71BA00 <= icao <= 0x71BF99:
            return "HL" + hex(icao - 0x71BA00 + 0x7200)[2:]
        if 0x71C000 <= icao <= 0x71C099:
            return "HL" + hex(icao - 0x71C000 + 0x8000)[2:]
        if 0x71C200 <= icao <= 0x71C299:
            return "HL" + hex(icao - 0x71C200 + 0x8200)[2:]
        return None

    # Japan (JAxxxx)
    @staticmethod
    def ja_reg(icao: int):
        result = "JA"
        offset = icao - 0x840000
        if icao < 0 or icao >= 229840:
            return None

        # First is a digit
        x = int(offset / 22984)
        if x < 0 or x > 9:
            return None
        result += str(x)
        offset %= 22984

        # Second is a digit
        x = int(offset / 916)
        if x < 0 or x > 9:
            return None
        result += str(x)
        offset %= 916

        # Third and fourth are letters
        if offset >= 340:
            offset -= 340;
            x = int(offset / 24)
            return result + LIMITED_ALPHABET[x] + LIMITED_ALPHABET[offset % 24]

        # Third is a digit, Fourth is a digit or a letter
        x = int(offset / 34)
        result += str(x);
        offset %= 34
        if offset < 10:
            # Fourth is a digit
            return result + str(offset)
        else:
            # Fourth is a letter
            return result + LIMITED_ALPHABET[offset - 10]

    # United States (Nxxxx)
    @staticmethod
    def n_reg(icao: int):
        result = "N"
        offset = icao - 0xA00001
        if offset < 0 or offset >= 915399:
            return None

        x = int(offset / 101711) + 1
        result += str(x)
        offset %= 101711
        if offset <= 600:
            # Na, NaA .. NaZ, NaAA .. NaZZ
            return result + IcaoRegistration.n_letters(offset)

        # Na0* .. Na9*
        offset -= 601
        x = int(offset / 10111)
        result += str(x)
        offset %= 10111
        if offset <= 600:
            # Nab, NabA..NabZ, NabAA..NabZZ
            return result + IcaoRegistration.n_letters(offset)

        # Nab0* .. Nab9*
        offset -= 601
        x = int(offset / 951)
        result += str(x)
        offset %= 951
        if offset <= 600:
            # Nabc, NabcA .. NabcZ, NabcAA .. NabcZZ
            return result + IcaoRegistration.n_letters(offset)

        # Nabc0* .. Nabc9*
        offset -= 601
        x = int(offset / 35)
        result += str(x)
        offset %= 35
        if offset <= 24:
            # Nabcd, NabcdA .. NabcdZ
            return result + IcaoRegistration.n_letter(offset)
        else:
            # Nabcd0 .. Nabcd9
            return result + str(offset - 25)

    @staticmethod
    def n_letters(x: int):
        if x <= 0:
            return ""
        else:
            x -= 1
            return LIMITED_ALPHABET[int(x / 25)] + IcaoRegistration.n_letter(x % 25)

    @staticmethod
    def n_letter(x: int):
        if x <= 0:
            return ""
        else:
            x -= 1
            return LIMITED_ALPHABET[x]


class StrideMapping(object):
    @staticmethod
    def find(icao: int):
        for mapping in STRIDE_MAPPINGS:
            result = mapping.getRegistration(icao)
            if result is not None:
                return result
        return None

    def __init__(self, start: int, s1: int, s2: int, prefix: str, first: str = None, last: str = None, alphabet: str = None):
        self.start  = start
        self.s1     = s1 
        self.s2     = s2
        self.prefix = prefix 
        self.first  = first
        self.last   = last
        self.alphabet = FULL_ALPHABET if alphabet is None else alphabet

        if not first:
            self.offset = 0
        else:
            x1 = self.alphabet.find(first[0])
            x2 = self.alphabet.find(first[1])
            x3 = self.alphabet.find(first[2])
            self.offset = x1 * s1 + x2 * s2 + x3

        if not last:
            x = len(self.alphabet) - 1
            self.end = self.start - self.offset + x * s1 + x * s2 + x
        else:
            x1 = self.alphabet.find(last[0])
            x2 = self.alphabet.find(last[1])
            x3 = self.alphabet.find(last[2])
            self.end = self.start - self.offset + x1 * s1 + x2 * s2 + x3

    def contains(self, icao: int):
        return self.start <= icao <= self.end

    def getRegistration(self, icao: int):
        if not self.contains(icao):
            return None

        offset = icao - self.start + self.offset
        x1 = int(offset / self.s1)
        offset %= self.s1
        x2 = int(offset / self.s2)
        offset %= self.s2
        x3 = offset

        al = len(self.alphabet)
        if 0 <= x1 < al and 0 <= x2 < al and 0 <= x3 < al:
            return self.prefix + self.alphabet[x1] + self.alphabet[x2] + self.alphabet[x3]
        else:
            return None


class NumericMapping(object):
    @staticmethod
    def find(icao: int):
        for mapping in NUMERIC_MAPPINGS:
            result = mapping.getRegistration(icao)
            if result is not None:
                return result
        return None

    def __init__(self, start: int, first: int, count: int, template: str):
        self.start    = start
        self.end      = start + count - 1
        self.first    = first
        self.count    = count
        self.template = template

    def contains(self, icao: int):
        return self.start <= icao <= self.end

    def getRegistration(self, icao: int):
        if not self.contains(icao):
            return None

        result = str(icao - self.start + self.first)
        return self.template[:len(self.template)-len(result)] + result


class IcaoCountry(object):
    @staticmethod
    def find(icao: int):
        for x in ICAO_COUNTRIES:
            if x.contains(icao):
                return (x.getCountryName(), x.getCountryCode())
        return None

    def __init__(self, start: int, end: int, code: str, name: str):
        self.start = start
        self.end   = end 
        self.code  = code
        self.name  = name

    def contains(self, icao: int):
        return self.start <= icao <= self.end

    def getCountryName(self):
        return self.name

    def getCountryCode(self):
        return self.code


# 24 characters, without I/O
LIMITED_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"

# 26 characters
FULL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Numeric suffixes assigned with a regular pattern
# start    : start hexid in range
# first    : first numeric registration
# count    : number of numeric registrations
# template : template, trailing characters replaced with the number
NUMERIC_MAPPINGS = [
    NumericMapping(0x140000, 0,    100000, "RA-00000"),
    NumericMapping(0x0B03E8, 1000, 1000,   "CU-T0000"),
]

# Three-letter suffixes assigned with a regular pattern
# start    : first hexid of range
# s1       : major stride (interval between different first letters)
# s2       : minor stride (interval between different second letters)
# prefix   : the registration prefix
# alphabet : the alphabet to use (defaults to full_alphabet)
# first    : the suffix to use at the start of the range (default: AAA)
# last     : the last valid suffix in the range (default: ZZZ)
STRIDE_MAPPINGS = [
    # South African stride mapping apparently no longer in use
    #StrideMapping(0x008011, 26*26, 26, "ZS-"),

    StrideMapping(0x380000, 1024,  32, "F-B"),
    StrideMapping(0x388000, 1024,  32, "F-I"),
    StrideMapping(0x390000, 1024,  32, "F-G"),
    StrideMapping(0x398000, 1024,  32, "F-H"),
    StrideMapping(0x3A0000, 1024,  32, "F-O"),

    StrideMapping(0x3C4421, 1024,  32, "D-A", "AAA", "OZZ"),
    StrideMapping(0x3C0001, 26*26, 26, "D-A", "PAA", "ZZZ"),
    StrideMapping(0x3C8421, 1024,  32, "D-B", "AAA", "OZZ"),
    StrideMapping(0x3C2001, 26*26, 26, "D-B", "PAA", "ZZZ"),
    StrideMapping(0x3CC000, 26*26, 26, "D-C"),
    StrideMapping(0x3D04A8, 26*26, 26, "D-E"),
    StrideMapping(0x3D4950, 26*26, 26, "D-F"),
    StrideMapping(0x3D8DF8, 26*26, 26, "D-G"),
    StrideMapping(0x3DD2A0, 26*26, 26, "D-H"),
    StrideMapping(0x3E1748, 26*26, 26, "D-I"),

    StrideMapping(0x448421, 1024,  32, "OO-"),
    StrideMapping(0x458421, 1024,  32, "OY-"),
    StrideMapping(0x460000, 26*26, 26, "OH-"),
    StrideMapping(0x468421, 1024,  32, "SX-"),
    StrideMapping(0x490421, 1024,  32, "CS-"),
    StrideMapping(0x4A0421, 1024,  32, "YR-"),
    StrideMapping(0x4B8421, 1024,  32, "TC-"),
    StrideMapping(0x740421, 1024,  32, "JY-"),
    StrideMapping(0x760421, 1024,  32, "AP-"),
    StrideMapping(0x768421, 1024,  32, "9V-"),
    StrideMapping(0x778421, 1024,  32, "YK-"),
    StrideMapping(0xC00001, 26*26, 26, "C-F"),
    StrideMapping(0xC044A9, 26*26, 26, "C-G"),
    StrideMapping(0xE01041, 4096,  64, "LV-"),
]

# Mostly generated from the assignment table in the appendix to Chapter 9
# of Annex 10 Vol III, Second Edition, July 2007 (with amendments through
# 88-A, 14/11/2013)
ICAO_COUNTRIES = [
    IcaoCountry(0x004000, 0x0043FF, "ZW", "Zimbabwe"),
    IcaoCountry(0x006000, 0x006FFF, "MZ", "Mozambique"),
    IcaoCountry(0x008000, 0x00FFFF, "ZA", "South Africa"),
    IcaoCountry(0x010000, 0x017FFF, "EG", "Egypt"),
    IcaoCountry(0x018000, 0x01FFFF, "LY", "Lybia"),
    IcaoCountry(0x020000, 0x027FFF, "MA", "Morocco"),
    IcaoCountry(0x028000, 0x02FFFF, "TN", "Tunisia"),
    IcaoCountry(0x030000, 0x0303FF, "BW", "Botswana"),
    IcaoCountry(0x032000, 0x032FFF, "BI", "Burundi"),
    IcaoCountry(0x034000, 0x034FFF, "CM", "Cameroon"),
    IcaoCountry(0x035000, 0x0353FF, "KM", "Comoros"),
    # "CD" for Democratic Republic of Congo, "CG" for Republic of Congo
    IcaoCountry(0x036000, 0x036FFF, "CD", "DR Congo"),
    IcaoCountry(0x038000, 0x038FFF, "CI", "Cote d'Ivoire"),
    IcaoCountry(0x03E000, 0x03EFFF, "GA", "Gabon"),
    IcaoCountry(0x040000, 0x040FFF, "ET", "Ethiopia"),
    IcaoCountry(0x042000, 0x042FFF, "GQ", "Equatorial Guinea"),
    IcaoCountry(0x044000, 0x044FFF, "GH", "Ghana"),
    IcaoCountry(0x046000, 0x046FFF, "GN", "Guinea"),
    IcaoCountry(0x048000, 0x0483FF, "GW", "Guinea-Bissau"),
    IcaoCountry(0x04A000, 0x04A3FF, "LS", "Lesotho"),
    IcaoCountry(0x04C000, 0x04CFFF, "KE", "Kenya"),
    IcaoCountry(0x050000, 0x050FFF, "LR", "Liberia"),
    IcaoCountry(0x054000, 0x054FFF, "MG", "Madagascar"),
    IcaoCountry(0x058000, 0x058FFF, "MW", "Malawi"),
    IcaoCountry(0x05A000, 0x05A3FF, "MV", "Maldives"),
    IcaoCountry(0x05C000, 0x05CFFF, "ML", "Mali"),
    IcaoCountry(0x05E000, 0x05E3FF, "MR", "Mauritania"),
    IcaoCountry(0x060000, 0x0603FF, "MU", "Mauritius"),
    IcaoCountry(0x062000, 0x062FFF, "NE", "Niger"),
    IcaoCountry(0x064000, 0x064FFF, "NG", "Nigeria"),
    IcaoCountry(0x068000, 0x068FFF, "UG", "Uganda"),
    IcaoCountry(0x06A000, 0x06A3FF, "QA", "Qatar"),
    IcaoCountry(0x06C000, 0x06CFFF, "CF", "Central African Republic"),
    IcaoCountry(0x06E000, 0x06EFFF, "RW", "Rwanda"),
    IcaoCountry(0x070000, 0x070FFF, "SN", "Senegal"),
    IcaoCountry(0x074000, 0x0743FF, "SC", "Seychelles"),
    IcaoCountry(0x076000, 0x0763FF, "SL", "Sierra Leone"),
    IcaoCountry(0x078000, 0x078FFF, "SO", "Somalia"),
    IcaoCountry(0x07A000, 0x07A3FF, "SZ", "Eswatini"),
    IcaoCountry(0x07C000, 0x07CFFF, "SD", "Sudan"),
    IcaoCountry(0x080000, 0x080FFF, "TZ", "Tanzania"),
    IcaoCountry(0x084000, 0x084FFF, "TD", "Chad"),
    IcaoCountry(0x088000, 0x088FFF, "TG", "Togo"),
    IcaoCountry(0x08A000, 0x08AFFF, "ZM", "Zambia"),
    IcaoCountry(0x08C000, 0x08CFFF, "CD", "Congo"),
    IcaoCountry(0x090000, 0x090FFF, "AO", "Angola"),
    IcaoCountry(0x094000, 0x0943FF, "BJ", "Benin"),
    IcaoCountry(0x096000, 0x0963FF, "CV", "Cabo Verde"),
    IcaoCountry(0x098000, 0x0983FF, "DJ", "Djibouti"),
    IcaoCountry(0x09A000, 0x09AFFF, "GM", "Gambia"),
    IcaoCountry(0x09C000, 0x09CFFF, "BF", "Burkina Faso"),
    IcaoCountry(0x09E000, 0x09E3FF, "ST", "Sao Tome and Principe"),
    IcaoCountry(0x0A0000, 0x0A7FFF, "DZ", "Algeria"),
    IcaoCountry(0x0A8000, 0x0A8FFF, "BS", "Bahamas"),
    IcaoCountry(0x0AA000, 0x0AA3FF, "BB", "Barbados"),
    IcaoCountry(0x0AB000, 0x0AB3FF, "BZ", "Belize"),
    IcaoCountry(0x0AC000, 0x0ACFFF, "CO", "Colombia"),
    IcaoCountry(0x0AE000, 0x0AEFFF, "CR", "Costa Rica"),
    IcaoCountry(0x0B0000, 0x0B0FFF, "CU", "Cuba"),
    IcaoCountry(0x0B2000, 0x0B2FFF, "SV", "El Salvador"),
    IcaoCountry(0x0B4000, 0x0B4FFF, "GT", "Guatemala"),
    IcaoCountry(0x0B6000, 0x0B6FFF, "GY", "Guyana"),
    IcaoCountry(0x0B8000, 0x0B8FFF, "HT", "Haiti"),
    IcaoCountry(0x0BA000, 0x0BAFFF, "HN", "Honduras"),
    IcaoCountry(0x0BC000, 0x0BC3FF, "VC", "Saint Vincent and Grenadines"),
    IcaoCountry(0x0BE000, 0x0BEFFF, "JM", "Jamaica"),
    IcaoCountry(0x0C0000, 0x0C0FFF, "NI", "Nicaragua"),
    IcaoCountry(0x0C2000, 0x0C2FFF, "PA", "Panama"),
    IcaoCountry(0x0C4000, 0x0C4FFF, "DO", "Dominican Republic"),
    IcaoCountry(0x0C6000, 0x0C6FFF, "TT", "Trinidad and Tobago"),
    IcaoCountry(0x0C8000, 0x0C8FFF, "SR", "Suriname"),
    IcaoCountry(0x0CA000, 0x0CA3FF, "AG", "Antigua and Barbuda"),
    IcaoCountry(0x0CC000, 0x0CC3FF, "GD", "Grenada"),
    IcaoCountry(0x0D0000, 0x0D7FFF, "MX", "Mexico"),
    IcaoCountry(0x0D8000, 0x0DFFFF, "VE", "Venezuela"),
    IcaoCountry(0x100000, 0x1FFFFF, "RU", "Russia"),
    IcaoCountry(0x201000, 0x2013FF, "NA", "Namibia"),
    IcaoCountry(0x202000, 0x2023FF, "ER", "Eritrea"),
    IcaoCountry(0x300000, 0x33FFFF, "IT", "Italy"),
    IcaoCountry(0x340000, 0x37FFFF, "ES", "Spain"),
    IcaoCountry(0x380000, 0x3BFFFF, "FR", "France"),
    IcaoCountry(0x3C0000, 0x3FFFFF, "DE", "Germany"),

    # UK territories are officially part of the UK range, so adding
    # extra entries that are above the UK and thus take precedence
    IcaoCountry(0x400000, 0x4001BF, "BM", "Bermuda"),
    IcaoCountry(0x4001C0, 0x4001FF, "KY", "Cayman Islands"),
    IcaoCountry(0x400300, 0x4003FF, "TC", "Turks and Caicos"),
    IcaoCountry(0x424135, 0x4241F2, "KY", "Cayman Islands"),
    IcaoCountry(0x424200, 0x4246FF, "BM", "Bermuda"),
    IcaoCountry(0x424700, 0x424899, "KY", "Cayman Islands"),
    IcaoCountry(0x424B00, 0x424BFF, "IM", "Isle of Man"),
    IcaoCountry(0x43BE00, 0x43BEFF, "BM", "Bermuda"),
    IcaoCountry(0x43E700, 0x43EAFD, "IM", "Isle of Man"),
    IcaoCountry(0x43EAFE, 0x43EEFF, "GG", "Guernsey"),
    # Catch the rest of the United Kingdom
    IcaoCountry(0x400000, 0x43FFFF, "GB", "United Kingdom"),

    IcaoCountry(0x440000, 0x447FFF, "AT", "Austria"),
    IcaoCountry(0x448000, 0x44FFFF, "BE", "Belgium"),
    IcaoCountry(0x450000, 0x457FFF, "BG", "Bulgaria"),
    IcaoCountry(0x458000, 0x45FFFF, "DK", "Denmark"),
    IcaoCountry(0x460000, 0x467FFF, "FI", "Finland"),
    IcaoCountry(0x468000, 0x46FFFF, "GR", "Greece"),
    IcaoCountry(0x470000, 0x477FFF, "HU", "Hungary"),
    IcaoCountry(0x478000, 0x47FFFF, "NO", "Norway"),
    IcaoCountry(0x480000, 0x487FFF, "NL", "Netherlands"),
    IcaoCountry(0x488000, 0x48FFFF, "PL", "Poland"),
    IcaoCountry(0x490000, 0x497FFF, "PT", "Portugal"),
    IcaoCountry(0x498000, 0x49FFFF, "CZ", "Czechia"),
    IcaoCountry(0x4A0000, 0x4A7FFF, "RO", "Romania"),
    IcaoCountry(0x4A8000, 0x4AFFFF, "SE", "Sweden"),
    IcaoCountry(0x4B0000, 0x4B7FFF, "CH", "Switzerland"),
    IcaoCountry(0x4B8000, 0x4BFFFF, "TR", "Turkey"),
    IcaoCountry(0x4C0000, 0x4C7FFF, "RS", "Serbia"),
    IcaoCountry(0x4C8000, 0x4C83FF, "CY", "Cyprus"),
    IcaoCountry(0x4CA000, 0x4CAFFF, "IE", "Ireland"),
    IcaoCountry(0x4CC000, 0x4CCFFF, "IS", "Iceland"),
    IcaoCountry(0x4D0000, 0x4D03FF, "LU", "Luxembourg"),
    IcaoCountry(0x4D2000, 0x4D2FFF, "MT", "Malta"),
    IcaoCountry(0x4D4000, 0x4D43FF, "MC", "Monaco"),
    IcaoCountry(0x500000, 0x5003FF, "SM", "San Marino"),
    IcaoCountry(0x501000, 0x5013FF, "AL", "Albania"),
    IcaoCountry(0x501C00, 0x501FFF, "HR", "Croatia"),
    IcaoCountry(0x502C00, 0x502FFF, "LV", "Latvia"),
    IcaoCountry(0x503C00, 0x503FFF, "LT", "Lithuania"),
    IcaoCountry(0x504C00, 0x504FFF, "MD", "Moldova"),
    IcaoCountry(0x505C00, 0x505FFF, "SK", "Slovakia"),
    IcaoCountry(0x506C00, 0x506FFF, "SI", "Slovenia"),
    IcaoCountry(0x507C00, 0x507FFF, "UZ", "Uzbekistan"),
    IcaoCountry(0x508000, 0x50FFFF, "UA", "Ukraine"),
    IcaoCountry(0x510000, 0x5103FF, "BY", "Belarus"),
    IcaoCountry(0x511000, 0x5113FF, "EE", "Estonia"),
    IcaoCountry(0x512000, 0x5123FF, "MK", "Macedonia"),
    IcaoCountry(0x513000, 0x5133FF, "BA", "Bosnia and Herzegovina"),
    IcaoCountry(0x514000, 0x5143FF, "GE", "Georgia"),
    IcaoCountry(0x515000, 0x5153FF, "TJ", "Tajikistan"),
    IcaoCountry(0x516000, 0x5163FF, "ME", "Montenegro"),
    IcaoCountry(0x600000, 0x6003FF, "AM", "Armenia"),
    IcaoCountry(0x600800, 0x600BFF, "AZ", "Azerbaijan"),
    IcaoCountry(0x601000, 0x6013FF, "KG", "Kyrgyzstan"),
    IcaoCountry(0x601800, 0x601BFF, "TM", "Turkmenistan"),
    IcaoCountry(0x680000, 0x6803FF, "BT", "Bhutan"),
    IcaoCountry(0x681000, 0x6813FF, "FM", "Micronesia"),
    IcaoCountry(0x682000, 0x6823FF, "MN", "Mongolia"),
    IcaoCountry(0x683000, 0x6833FF, "KZ", "Kazakhstan"),
    IcaoCountry(0x684000, 0x6843FF, "PW", "Palau"),
    IcaoCountry(0x700000, 0x700FFF, "AF", "Afghanistan"),
    IcaoCountry(0x702000, 0x702FFF, "BD", "Bangladesh"),
    IcaoCountry(0x704000, 0x704FFF, "MM", "Myanmar"),
    IcaoCountry(0x706000, 0x706FFF, "KW", "Kuwait"),
    IcaoCountry(0x708000, 0x708FFF, "LA", "Laos"),
    IcaoCountry(0x70A000, 0x70AFFF, "NP", "Nepal"),
    IcaoCountry(0x70C000, 0x70C3FF, "OM", "Oman"),
    IcaoCountry(0x70E000, 0x70EFFF, "KH", "Cambodia"),
    IcaoCountry(0x710000, 0x717FFF, "SA", "Saudi Arabia"),
    IcaoCountry(0x718000, 0x71FFFF, "KR", "South Korea"),
    IcaoCountry(0x720000, 0x727FFF, "KP", "North Korea"),
    IcaoCountry(0x728000, 0x72FFFF, "IQ", "Iraq"),
    IcaoCountry(0x730000, 0x737FFF, "IR", "Iran"),
    IcaoCountry(0x738000, 0x73FFFF, "IL", "Israel"),
    IcaoCountry(0x740000, 0x747FFF, "JO", "Jordan"),
    IcaoCountry(0x748000, 0x74FFFF, "LB", "Lebanon"),
    IcaoCountry(0x750000, 0x757FFF, "MY", "Malaysia"),
    IcaoCountry(0x758000, 0x75FFFF, "PH", "Philippines"),
    IcaoCountry(0x760000, 0x767FFF, "PK", "Pakistan"),
    IcaoCountry(0x768000, 0x76FFFF, "SG", "Singapore"),
    IcaoCountry(0x770000, 0x777FFF, "LK", "Sri Lanka"),
    IcaoCountry(0x778000, 0x77FFFF, "SY", "Syria"),
    IcaoCountry(0x789000, 0x789FFF, "HK", "Hong Kong"),
    IcaoCountry(0x780000, 0x7BFFFF, "CN", "China"),
    IcaoCountry(0x7C0000, 0x7FFFFF, "AU", "Australia"),
    IcaoCountry(0x800000, 0x83FFFF, "IN", "India"),
    IcaoCountry(0x840000, 0x87FFFF, "JP", "Japan"),
    IcaoCountry(0x880000, 0x887FFF, "TH", "Thailand"),
    IcaoCountry(0x888000, 0x88FFFF, "VN", "Viet Nam"),
    IcaoCountry(0x890000, 0x890FFF, "YE", "Yemen"),
    IcaoCountry(0x894000, 0x894FFF, "BH", "Bahrain"),
    IcaoCountry(0x895000, 0x8953FF, "BN", "Brunei"),
    IcaoCountry(0x896000, 0x896FFF, "AE", "United Arab Emirates"),
    IcaoCountry(0x897000, 0x8973FF, "SB", "Solomon Islands"),
    IcaoCountry(0x898000, 0x898FFF, "PG", "Papua New Guinea"),
    IcaoCountry(0x899000, 0x8993FF, "TW", "Taiwan"),
    IcaoCountry(0x8A0000, 0x8A7FFF, "ID", "Indonesia"),
    IcaoCountry(0x900000, 0x9003FF, "MH", "Marshall Islands"),
    IcaoCountry(0x901000, 0x9013FF, "SK", "Cook Islands"),
    IcaoCountry(0x902000, 0x9023FF, "WS", "Samoa"),
    IcaoCountry(0xA00000, 0xAFFFFF, "US", "United States"),
    IcaoCountry(0xC00000, 0xC3FFFF, "CA", "Canada"),
    IcaoCountry(0xC80000, 0xC87FFF, "NZ", "New Zealand"),
    IcaoCountry(0xC88000, 0xC88FFF, "FJ", "Fiji"),
    IcaoCountry(0xC8A000, 0xC8A3FF, "NR", "Nauru"),
    IcaoCountry(0xC8C000, 0xC8C3FF, "LC", "Saint Lucia"),
    IcaoCountry(0xC8D000, 0xC8D3FF, "TO", "Tonga"),
    IcaoCountry(0xC8E000, 0xC8E3FF, "KI", "Kiribati"),
    IcaoCountry(0xC90000, 0xC903FF, "VU", "Vanuatu"),
    IcaoCountry(0xE00000, 0xE3FFFF, "AR", "Argentina"),
    IcaoCountry(0xE40000, 0xE7FFFF, "BR", "Brazil"),
    IcaoCountry(0xE80000, 0xE80FFF, "CL", "Chile"),
    IcaoCountry(0xE84000, 0xE84FFF, "EC", "Ecuador"),
    IcaoCountry(0xE88000, 0xE88FFF, "PY", "Paraguay"),
    IcaoCountry(0xE8C000, 0xE8CFFF, "PE", "Peru"),
    IcaoCountry(0xE90000, 0xE90FFF, "UY", "Uruguay"),
    IcaoCountry(0xE94000, 0xE94FFF, "BO", "Bolivia"),
    IcaoCountry(0xF00000, 0xF07FFF, None, "ICAO (temporary)"),
    IcaoCountry(0xF09000, 0xF093FF, None, "ICAO (special use)"),

    # Block assignments mentioned in Chapter 9 section 4, at the end so they
    # are only used if nothing above applies
    IcaoCountry(0x200000, 0x27FFFF, None, "Unassigned (AFI region)"),
    IcaoCountry(0x280000, 0x28FFFF, None, "Unassigned (SAM region)"),
    IcaoCountry(0x500000, 0x5FFFFF, None, "Unassigned (EUR / NAT regions)"),
    IcaoCountry(0x600000, 0x67FFFF, None, "Unassigned (MID region)"),
    IcaoCountry(0x680000, 0x6FFFFF, None, "Unassigned (ASIA region)"),
    IcaoCountry(0x900000, 0x9FFFFF, None, "Unassigned (NAM / PAC regions)"),
    IcaoCountry(0xB00000, 0xBFFFFF, None, "Unassigned (reserved for future use)"),
    IcaoCountry(0xEC0000, 0xEFFFFF, None, "Unassigned (CAR region)"),
    IcaoCountry(0xD00000, 0xDFFFFF, None, "Unassigned (reserved for future use)"),
    IcaoCountry(0xF00000, 0xFFFFFF, None, "Unassigned (reserved for future use)"),
]
