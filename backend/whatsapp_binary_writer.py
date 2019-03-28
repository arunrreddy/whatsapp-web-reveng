from whatsapp_defines import WATags, WASingleByteTokens, WADoubleByteTokens, WAWebMessageInfo
from utilities import getNumValidKeys, encodeUTF8, ceil, eprint


class WABinaryWriter:
    def __init__(self):
        self.data = []

    def getData(self):
        eprint('GetData: ', self.data)
        return "".join(map(chr, self.data))

    def pushByte(self, value):
        eprint('PushByte: ', value)
        self.data.append(value)
        eprint(self.data)

    def pushIntN(self, value, n, littleEndian = False):
        eprint('PushIntN: ', value, n, littleEndian)
        for i in range(n):
            currShift = i if littleEndian else n-1-i
            self.pushByte((value >> (currShift*8)) & 0xFF)

    def pushInt20(self, value):
        eprint('PushInt20: ', value)
        self.pushBytes(
            [(value >> 16) & 0x0F, (value >> 8) & 0xFF, value & 0xFF])

    def pushInt8(self, value):
        eprint('PushInt8: ', value)
        self.pushIntN(value, 1, False)

    def pushInt16(self, value):
        eprint('PushInt16: ', value)
        self.pushIntN(value, 2, False)

    def pushInt32(self, value):
        eprint('PushInt32: ', value)
        self.pushIntN(value, 4, False)

    def pushInt64(self, value):
        eprint('PushInt64: ', value)
        self.pushIntN(value, 8, False)

    def pushBytes(self, incomingBytes):
        eprint('PushBytes: ', incomingBytes)
        self.data += incomingBytes

    def pushString(self, strng): # look into this after debug
        eprint('PushString: ', strng)
        eprint('EncodedString: ', encodeUTF8(strng))
        self.data += map(ord, encodeUTF8(strng))
        eprint('Data after pushing string: ', self.data)

    def writeByteLength(self, length):
        eprint('WriteByteLength: ', length)
        if length >= 4294967296:
            raise ValueError(
                "string too large to encode (len = " + str(length) + "): " + str)

        if length >= (1 << 20):
            self.pushByte(WATags.BINARY_32)
            self.pushInt32(length)
        elif length >= 256:
            self.pushByte(WATags.BINARY_20)
            self.pushInt20(length)
        else:
            self.pushByte(WATags.BINARY_8)
            self.pushInt8(length)
    
    # revisit func
    def writeNode(self, node):
        eprint('WriteNode: ', node)
        if node is None:
            return
        if not isinstance(node, list) or len(node) != 3:
            raise ValueError("invalid node")
        numAttributes = getNumValidKeys(node[1]) if bool(node[1]) else 0

        self.writeListStart(2*numAttributes + 1 + (1 if bool(node[2]) else 0))
        self.writeString(node[0])
        self.writeAttributes(node[1])
        self.writeChildren(node[2])

    def writeString(self, token, i=None):
        eprint('WriteString: ', token, i)
        if not isinstance(token, str):
            raise ValueError("invalid string")

        if not bool(i) and token == "c.us":
            self.writeToken(WASingleByteTokens.index("s.whatsapp.net"))
            return

        if token not in WASingleByteTokens:
            jidSepIndex = token.index("@") if "@" in token else -1
            if jidSepIndex < 1:
                self.writeStringRaw(token)
            else:
                self.writeJid(token[:jidSepIndex], token[jidSepIndex+1:])
        else:
            tokenIndex = WASingleByteTokens.index(token)
            if tokenIndex < WATags.SINGLE_BYTE_MAX:
                self.writeToken(tokenIndex)
            else:
                singleByteOverflow = tokenIndex - WATags.SINGLE_BYTE_MAX
                dictionaryIndex = singleByteOverflow >> 8
                if dictionaryIndex < 0 or dictionaryIndex > 3:
                    raise ValueError(
                        "double byte dictionary token out of range: " + token + " " + str(tokenIndex))
                self.writeToken(WATags.DICTIONARY_0 + dictionaryIndex)
                self.writeToken(singleByteOverflow % 256)

    def writeStringRaw(self, strng):
        eprint('WriteStringRaw: ', strng)
        strng = encodeUTF8(strng)
        eprint('Encoded String: ', strng)
        self.writeByteLength(len(strng))
        self.pushString(strng)

    def writeJid(self, jidLeft, jidRight):
        eprint('WriteJid: ', jidLeft, jidRight, WATags.JID_PAIR, WATags.LIST_EMPTY)
        self.pushByte(WATags.JID_PAIR)
        if jidLeft is not None and len(jidLeft) > 0:
            self.writePackedBytes(jidLeft)
        else:
            self.writeToken(WATags.LIST_EMPTY)
        self.writeString(jidRight, False)

    def writeToken(self, token):
        eprint('WriteToken: ', token)
        eprint('Length: ', len(WASingleByteTokens))
        if(token < len(WASingleByteTokens)):
            self.pushByte(token)
        elif token <= 500:
            raise ValueError("invalid token")

    def writeAttributes(self, attrs):
        eprint('WriteAttributes: ', attrs)
        if attrs is None:
            return
        for key, value in attrs.iteritems():
            if value is not None:
                self.writeString(key, False)
                self.writeString(value, False)

    def writeChildren(self, children):
        eprint('WriteChildren: ', children)
        if children is None:
            return

        if isinstance(children, str):
            self.writeString(children, True)
        elif isinstance(children, bytes):
            self.writeByteLength(len(children))
            self.pushBytes(children)
        else:
            if not isinstance(children, list):
                raise ValueError("invalid children")
            self.writeListStart(len(children))
            for c in children:
                self.writeNode(c)

    def writeListStart(self, listSize):
        eprint('WriteListStart: ', listSize, WATags.LIST_EMPTY, WATags.LIST_8, WATags.LIST_16)
        if listSize == 0:
            self.pushByte(WATags.LIST_EMPTY)
        elif listSize < 256:
            self.pushByte(WATags.LIST_8)
            self.pushInt8(listSize)
        else:
            self.pushByte(WATags.LIST_16)
            self.pushInt16(listSize)

    def writePackedBytes(self, strng):
        eprint('WritePackedBytes: ', strng, WATags.NIBBLE_8, WATags.HEX_8)
        try:
            self.writePackedBytesImpl(strng, WATags.NIBBLE_8)
        except:
            self.writePackedBytesImpl(strng, WATags.HEX_8)

    def writePackedBytesImpl(self, strng, dataType):
        eprint('WritePackedBytesImpl: ', strng, dataType)
        strng = encodeUTF8(strng)
        eprint('Encoded string: ', strng)
        numBytes = len(strng)
        if numBytes > WATags.PACKED_MAX:
            raise ValueError(
                "too many bytes to nibble-encode: len = " + str(numBytes))

        self.pushByte(dataType)
        self.pushByte((128 if (numBytes % 2) != 0 else 0) | ceil(numBytes/2))

        for i in range(numBytes // 2):
            self.pushByte(self.packBytePair(
                dataType, strng[2*i:2*i+1], strng[2*i+1:2*i+2]))
        if (numBytes % 2) != 0:
            self.pushByte(self.packBytePair(
                dataType, strng[numBytes-1:], "\x00"))

    def packBytePair(self, packType, part1, part2):
        eprint('Pack byte pair: ', packType, part1, part2)
        if packType == WATags.NIBBLE_8:
            return (self.packNibble(part1) << 4) | self.packNibble(part2)
        elif packType == WATags.HEX_8:
            return (self.packHex(part1) << 4) | self.packHex(part2)
        else:
            raise ValueError("invalid byte pack type: " + str(packType))

    def packNibble(self, value):
        eprint('Pack nibble: ', value)
        if value >= "0" and value <= "9":
            return int(value)
        elif value == "-":
            return 10
        elif value == ".":
            return 11
        elif value == "\x00":
            return 15
        raise ValueError("invalid byte to pack as nibble: " + str(value))

    def packHex(self, value):
        eprint('Pack hex: ', value)
        if (value >= "0" and value <= "9") or (value >= "A" and value <= "F") or (value >= "a" and value <= "f"):
            return int(value, 16)
        elif value == "\x00":
            return 15
        raise ValueError("invalid byte to pack as hex: " + str(value))


def whatsappWriteBinary(node):
    stream = WABinaryWriter()
    stream.writeNode(node)
    return stream.getData()
