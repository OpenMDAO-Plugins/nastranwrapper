"""Defines NastranMaker, an intelligent bulk data replacer
for Nastran files."""
import re
from nastran_util import stringify

class NastranMaker(object):
    """A object that performs specified replacements conforming
    to the Nastran format.

    The goal of NastranMaker is to output a Nastran file with
    a set of variables replaced. It takes an existing Nastran file
    and variables. In order to retain as much data as possible,
    it replaces the variables in long format, allowing for 16
    characters, instead of 8.
    """


    def __init__(self, text):
        self.text = text
        self.names = {}

    def set(self, name, cid, fieldnum, value):
        """Records what should be replaced where.

        Instead of doing the replacing as we 
        are given the variables to replace, we'd like
        to do all the replacing at one time. Therefore, this
        function just records what should be replaced.

        name: str
        

        cid: int or str
        Specifies the id of the card.
        

        fieldnum: int
          What field should we modify?
        

        value: thing that can be passed to str
          What value should we put in?
            
        """
        self.names.setdefault((name, cid), []).append({"fieldnum": fieldnum, "value":value})

    def _nastran_set(self, name, cid, attrs, unique_int):
        """We go through the text that we have and make
        the needed substitution.

        name: str
        
        cid: int or str
            Specifies the id of the card.
            
        attrs: [{fieldnum: value_to_insert}]
            We may have to change a few fields for a given
            line. Those changes are stored in attrs.
            
        unique_int: int
            This integer is needed for writing out the
            continuations in the Nastran file. It must be
            unique within the file (!beware).
            
        """
        card = None
        for index, line in enumerate(self.text):
            if line.startswith(name):
                match = re.match("(?P<name>[a-zA-Z0-9*]*) +(?P<num>\d+) ", line)
                if match and \
                       (match.group("name") == name or \
                        match.group("name") == name + "*") \
                        and match.group("num") == str(cid):
                    if not card:
                        card = index
                    else:
                        raise RuntimeError("There were two cards with the " + \
                                        "same id. You don't want this. " + \
                                        "Two cards: " + match.group("name") +\
                                        " id: " + match.group("num"))

        if card is None:
            raise RuntimeError("Could not find card " + name + " with id " + str(cid))

        # are we dealing with a long card?
        long_card = False
        if self.text[card].startswith(name + "*") or \
               name.endswith("*"):
            long_card = True

        offset = 16 if long_card else 8
        divisions = 6 if long_card else 10

        # parse it up
        items = []
        current_row = card
        continuation = None
        while current_row < len(self.text) and \
                  (current_row == card or self.text[current_row].startswith(" ") or \
                   (continuation and
                    self.text[current_row].replace(" ", "").startswith(continuation))):
            # in both long and short forms, the first slot is 8 characters wide
            # then the rest are either 8 or 16 wide
            last_index = 0
            for i in [8 + i * offset for i in range(divisions)]:
                items.append(self.text[current_row][last_index:i])
                last_index = i

            # continuations are in the last slot
            if len(items[-1]) > 0:
                continuation = items[-1].replace(" ", "")
                if not continuation.startswith("+") and \
                       not continuation.startswith("*"):
                    raise RuntimeError("Your continuations should start" + \
                                    "with either * or +. `" + continuation + "` is not" + \
                                    "acceptable")

            current_row += 1

        # we want to delete the row(s) from the file
        del self.text[card:current_row]

        # now we add the field with the change applied
        # we're also going to conver the field to long
        # form and add it to the end of the file
        long_format = 16
        divisions = 6

        # change the value we're supposed to change
        for attr in attrs:
            fieldnum = attr["fieldnum"]
            value = attr["value"]

            #print "supposed to change", fieldnum, "to", value

            items[fieldnum] = stringify(value, length=long_format)

        # remove the continuations
        to_remove = None
        if not long_card:
            to_remove = [i for i in range(9, len(items), 10)] + \
                        [i for i in range(10, len(items), 10)]
        else:
            to_remove = [i for i in range(5, len(items), 6)] + \
                        [i for i in range(6, len(items), 6)]

        to_remove.sort(reverse=True)
        for i in to_remove:
            del items[i]


        # write it to the end of the file
        unique_int, new_rows = _items_to_long_form(items, unique_int)

        for row in new_rows[::-1]:
            self.text.insert(card, row)

        #print "\n".join(new_rows)
        return unique_int

    def _output(self, unique_id):
        """A little helper that just commits all the changes
        that should be made.

        This changes self.text"""
        for (name, cid), attrs in self.names.iteritems():
            unique_id = self._nastran_set(name, cid, attrs, unique_id)

    def write_to_file(self, file_handler, unique_int=10001):
        """After specifying the substitutions that should be made,
        write out the finished product.

        file_handler: file-like object
            Should provide a ``write`` and ``close`` function.

        unique_int: int
            Should be unique within the entire input file for Nastran
            to work.

        This changes ``self.text`` and then prints ``self.text`` to a file. So,
        calling ``write_to_file`` more than once is unnecessary, although it shouldn't
        actually change anything. Also note that the ``unique_int`` should
        be unique within the entire file."""

        self._output(unique_int)
        file_handler.write("\n".join(self.text))
        file_handler.close()



def _items_to_long_form(items, unique_int):
    """Convert to Nastran long form.

    This is a helper method to convert a list of items
    to a list of strings that represent Nastran long form."""
    if "*" not in items[0]:
        items[0] = items[0].strip() + "*"

    while len(items):
        if items[-1] == "":
            del items[-1]
        else: break

    # insert some continuations
    divisions = 4
    index = 1
    while index < len(items)-divisions:
        index += divisions
        continuation = "*" + str(unique_int)
        unique_int += 1
        items.insert(index, continuation)
        items.insert(index, continuation)
        index += 2

    final = []
    for index, item in enumerate(items):
        if index % 6 == 0:
            final.append(item.ljust(8))
        else:
            final[-1] += item.ljust(16)

    return unique_int, final
