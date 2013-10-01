#!/usr/bin/env python
# -- Content-Encoding: UTF-8 --
"""
Dependency-less LDAP filter parser for Python

:author: Thomas Calmant
:copyright: Copyright 2013, isandlaTech
:license: GPLv3
:version: 0.4
:status: Alpha

..

    This file is part of iPOPO.

    iPOPO is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    iPOPO is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with iPOPO. If not, see <http://www.gnu.org/licenses/>.
"""

from pelix.utilities import is_string
import inspect

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 4, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

ESCAPE_CHARACTER = '\\'
""" The LDAP escape character: \\"""

# Do not insert the ESCAPE CHARACTER in this list
ESCAPED_CHARACTERS = "()&|=<>~*+#,;'\""
"""
The characters to escape in an LDAP string.
See http://www.ldapexplorer.com/en/manual/109010000-ldap-filter-syntax.htm
"""

# ------------------------------------------------------------------------------

AND = 0
""" 'And' LDAP operation """

OR = 1
""" 'Or' LDAP operation """

NOT = 2
""" 'Not' LDAP operation """

# ------------------------------------------------------------------------------

class LDAPFilter(object):
    """
    Represents an LDAP filter
    """
    def __init__(self, operator):
        """
        Initializer
        """
        if operator not in (AND, OR, NOT):
            raise ValueError("Invalid operator: {0}".format(operator))

        self.subfilters = []
        self.operator = operator


    def __eq__(self, other):
        """
        Equality testing
        """
        if type(other) is not LDAPFilter:
            # Bad type
            return False

        if self.operator != other.operator:
            # Different operators
            return False

        # All sub-filters must match
        if len(self.subfilters) != len(other.subfilters):
            # Not the same size...
            return False

        for subfilter in self.subfilters:
            if subfilter not in other.subfilters:
                # Missing sub filter
                return False

        # Same content
        return True


    def __ne__(self, other):
        """
        Inequality testing
        """
        return not self.__eq__(other)


    def __repr__(self):
        """
        String description
        """
        return "{0}.get_ldap_filter({1!r})".format(__name__, self.__str__())


    def __str__(self):
        """
        String representation
        """
        return "({0}{1})".format(operator2str(self.operator),
               "".join([str(subfilter) for subfilter in self.subfilters]))


    def append(self, ldap_filter):
        """
        Appends a filter or a criterion to this filter

        :param ldap_filter: An LDAP filter or criterion
        :raise TypeError: If the parameter is not of a known type
        :raise ValueError: If the more than one filter is associated to a
                           NOT operator
        """
        if not isinstance(ldap_filter, (LDAPFilter, LDAPCriteria)):
            raise TypeError("Invalid filter type: {0}".format(
                                                type(ldap_filter).__name__))

        if len(self.subfilters) >= 1 and self.operator == NOT:
            raise ValueError("Not operator only handles one child")

        self.subfilters.append(ldap_filter)


    def matches(self, properties):
        """
        Tests if the given properties matches this LDAP filter and its children

        :param properties: A dictionary of properties
        :return: True if the properties matches this filter, else False
        """
        # Use a generator, and declare it outside of the method call
        # => seems to be quite a speed up trick
        generator = (criterion.matches(properties)
                     for criterion in self.subfilters)

        # Extract "if" from loops and use built-in methods
        if self.operator == OR:
            result = any(generator)

        else:
            result = all(generator)
            if self.operator == NOT:
                # Revert result
                return not result

        return result


    def normalize(self):
        """
        Returns the first meaningful object in this filter.
        """
        if not self.subfilters:
            # No sub-filters
            return None

        # New sub-filters list
        new_filters = []
        for subfilter in self.subfilters:
            # Normalize the sub-filter before storing it
            norm_filter = subfilter.normalize()
            if norm_filter is not None and norm_filter not in new_filters:
                new_filters.append(norm_filter)

        # Update the instance
        self.subfilters = new_filters

        size = len(self.subfilters)
        if size > 1:
            # Normal filter
            return self

        else:
            if self.operator == NOT:
                # NOT is the only operator to accept 1 operand
                return self

            else:
                # Return the only child as the filter object
                return self.subfilters[0].normalize()


class LDAPCriteria(object):
    """
    Represents an LDAP criterion
    """
    def __init__(self, name, value, comparator):
        """
        Sets up the criterion

        :raise ValueError: If one of the parameters is empty
        """
        if not name or not value or not comparator:
            # Refuse empty values
            raise ValueError("Invalid criterion parameter ({0}, {1}, {2})"\
                             .format(name, value, comparator))

        if not inspect.isroutine(comparator):
            # Ensure we have a valid comparator
            raise ValueError("Comparator must be a method: {0}", comparator)

        self.name = str(name)
        self.value = value
        self.comparator = comparator


    def __eq__(self, other):
        """
        Equality testing
        """
        if type(other) is not LDAPCriteria:
            # Bad type
            return False

        for member in ('name', 'comparator'):
            if getattr(self, member) != getattr(other, member):
                # Difference found
                return False

        if type(self.value) == type(other.value):
            # Same type: direct comparison
            result = self.value == other.value
            return result

        else:
            # Convert to strings for comparison
            return str(self.value) == str(other.value)


    def __ne__(self, other):
        """
        Inequality testing
        """
        return not self.__eq__(other)


    def __repr__(self):
        """
        String representation
        """
        return '{0}.get_ldap_filter({1!r})'.format(__name__, self.__str__())


    def __str__(self):
        """
        String description
        """
        return "({0}{1}{2})".format(escape_LDAP(self.name),
                                    comparator2str(self.comparator),
                                    escape_LDAP(str(self.value)))


    def matches(self, properties):
        """
        Tests if the given criterion matches this LDAP criterion

        :param properties: A dictionary of properties
        :return: True if the properties matches this criterion, else False
        """
        try:
            # Use the comparator
            return self.comparator(self.value, properties[self.name])

        except KeyError:
            # Criterion key is not in the properties
            return False


    def normalize(self):
        """
        Returns this criterion
        """
        return self

# ------------------------------------------------------------------------------

def comparator2str(comparator):
    """
    Converts an operator method to a string
    """
    if comparator in (_comparator_approximate, _comparator_approximate_star):
        return "~="

    elif comparator in (_comparator_eq, _comparator_star):
        return "="

    elif comparator == _comparator_le:
        return "<="

    elif comparator == _comparator_lt:
        return "<"

    elif comparator == _comparator_ge:
        return ">="

    elif comparator == _comparator_gt:
        return ">"

    return "??"


def operator2str(operator):
    """
    Converts an operator value to a string
    """
    if operator == AND:
        return '&'

    elif operator == OR:
        return '|'

    elif operator == NOT:
        return '!'

    return '<unknown>'


def escape_LDAP(ldap_string):
    """
    Escape a string to let it go in an LDAP filter

    :param ldap_string: The string to escape
    :return: The protected string
    """
    if ldap_string is None:
        return None

    assert is_string(ldap_string)

    if len(ldap_string) == 0:
        # No content
        return ldap_string

    # Protect escape character previously in the string
    ldap_string = ldap_string.replace(ESCAPE_CHARACTER, \
                                      ESCAPE_CHARACTER + ESCAPE_CHARACTER)

    # Leading space
    if ldap_string.startswith(" "):
        ldap_string = "\\ {0}".format(ldap_string[1:])

    # Trailing space
    if ldap_string.endswith(" "):
        ldap_string = "{0}\\ ".format(ldap_string[:-1])

    # Escape other characters
    for escaped in ESCAPED_CHARACTERS:
        ldap_string = ldap_string.replace(escaped, ESCAPE_CHARACTER + escaped)

    return ldap_string


def unescape_LDAP(ldap_string):
    """
    Unespaces an LDAP string

    :param ldap_string: The string to unescape
    :return: The unprotected string
    """
    if ldap_string is None:
        return None

    assert is_string(ldap_string)

    if ESCAPE_CHARACTER not in ldap_string:
        # No need to loop
        return ldap_string

    escaped = False
    result = ""

    for character in ldap_string:
        if not escaped and character == ESCAPE_CHARACTER:
            # Escape character found
            escaped = True

        else:
            # Copy the character
            escaped = False
            result += character

    return result

# ------------------------------------------------------------------------------

ITERABLES = (list, tuple, set)
""" The types that are considered iterable in comparators """

def _comparator_presence(_, tested_value):
    """
    Tests a filter which simply a joker, i.e. a value presence test
    """
    # The filter value is a joker : simple presence test
    if tested_value is None:
        return False

    elif hasattr(tested_value, "__len__"):
        # Refuse empty values
        return len(tested_value) != 0

    # Presence validated
    return True


def _comparator_star(filter_value, tested_value):
    """
    Tests a filter containing a joker
    """
    if isinstance(tested_value, ITERABLES):
        for value in tested_value:
            if _star_comparison(filter_value, value):
                return True

    else:
        return _star_comparison(filter_value, tested_value)


def _star_comparison(filter_value, tested_value):
    """
    Tests a filter containing a joker
    """
    if not is_string(tested_value):
        # Unhandled value type...
        return False

    parts = filter_value.split('*')

    i = 0
    last_part = len(parts) - 1

    idx = 0
    for part in parts:
        # Find the part in the tested value
        idx = tested_value.find(part, idx)

        if idx == -1:
            # Part not found
            return False

        if i == 0 and len(part) != 0 and idx != 0:
            # First part is not a star, but the tested value is not at
            # position 0 => Doesn't match
            return False

        if i == last_part and len(part) != 0 \
        and idx != len(tested_value) - len(part):
            # Last tested part is not at the end of the sequence
            return False

        # Be sure to test the next part
        idx += len(part)
        i += 1

    # Whole test passed
    return True


def _comparator_eq(filter_value, tested_value):
    """
    Tests if the filter value is equal to the tested value
    """
    if isinstance(tested_value, ITERABLES):
        # Convert the list items to strings
        for value in tested_value:
            # Try with the string conversion
            if not is_string(value):
                value = repr(value)

            if filter_value == value:
                # Match !
                return True

    # Standard comparison
    elif not is_string(tested_value):
        # String vs string representation
        return filter_value == repr(tested_value)

    else:
        # String vs string
        return filter_value == tested_value

    return False


def _comparator_approximate(filter_value, tested_value):
    """
    Tests if the filter value is nearly equal to the tested value.

    If the tested value is a string or an array of string, it compares their
    lower case forms
    """
    lower_filter_value = filter_value.lower()

    if is_string(tested_value):
        # Lower case comparison
        return _comparator_eq(lower_filter_value, tested_value.lower())

    elif hasattr(tested_value, '__iter__'):
        # Extract a list of strings
        new_tested = [value.lower() for value in tested_value \
                      if is_string(value)]

        if _comparator_eq(lower_filter_value, new_tested):
            # Value found in the strings
            return True

    # Compare the raw values
    return _comparator_eq(filter_value, tested_value) \
        or _comparator_eq(lower_filter_value, tested_value)


def _comparator_approximate_star(filter_value, tested_value):
    """
    Tests if the filter value, which contains a joker, is nearly equal to the
    tested value.

    If the tested value is a string or an array of string, it compares their
    lower case forms
    """
    lower_filter_value = filter_value.lower()

    if is_string(tested_value):
        # Lower case comparison
        return _comparator_star(lower_filter_value, tested_value.lower())

    elif hasattr(tested_value, '__iter__'):
        # Extract a list of strings
        new_tested = [value.lower() for value in tested_value \
                      if is_string(value)]

        if _comparator_star(lower_filter_value, new_tested):
            # Value found in the strings
            return True

    # Compare the raw values
    return _comparator_star(filter_value, tested_value) \
        or _comparator_star(lower_filter_value, tested_value)


def _comparator_le(filter_value, tested_value):
    """
    Tests if the filter value is greater than the tested value

    tested_value <= filter_value
    """
    return _comparator_lt(filter_value, tested_value) \
        or _comparator_eq(filter_value, tested_value)


def _comparator_lt(filter_value, tested_value):
    """
    Tests if the filter value is strictly greater than the tested value

    tested_value < filter_value
    """
    if is_string(filter_value):
        value_type = type(tested_value)
        try:
            # Try a conversion
            filter_value = value_type(filter_value)

        except (TypeError, ValueError):
            if value_type is int:
                # Integer/float comparison trick
                try:
                    filter_value = float(filter_value)

                except (TypeError, ValueError):
                    # None-float value
                    return False

            else:
                # Incompatible type
                return False

    try:
        return tested_value < filter_value

    except TypeError:
        # Incompatible type
        return False


def _comparator_ge(filter_value, tested_value):
    """
    Tests if the filter value is lesser than the tested value

    tested_value >= filter_value
    """
    return _comparator_gt(filter_value, tested_value) \
        or _comparator_eq(filter_value, tested_value)


def _comparator_gt(filter_value, tested_value):
    """
    Tests if the filter value is strictly lesser than the tested value

    tested_value > filter_value
    """
    if is_string(filter_value):
        value_type = type(tested_value)
        try:
            # Try a conversion
            filter_value = value_type(filter_value)

        except (TypeError, ValueError):
            if value_type is int:
                # Integer/float comparison trick
                try:
                    filter_value = float(filter_value)

                except (TypeError, ValueError):
                    # None-float value
                    return False

            else:
                # Incompatible type
                return False

    try:
        return tested_value > filter_value

    except TypeError:
        # Incompatible type
        return False


# ------------------------------------------------------------------------------

def _compute_comparator(string, idx):
    """
    Tries to compute the LDAP comparator at the given index

    Valid operators are :

    * = : equality
    * <= : less than
    * >= : greater than
    * ~= : approximate

    :param string: A LDAP filter string
    :param idx: An index in the given string
    :return: The corresponding operator, None if unknown
    """
    part1 = string[idx]
    if part1 == '=':
        # Equality
        return _comparator_eq

    elif len(string) < idx + 2:
        # Too short string
        return None

    elif string[idx + 1] != '=':
        # It's a "strict" operator
        if part1 == '<':
            # Strictly lesser
            return _comparator_lt

        elif part1 == '>':
            # Strictly greater
            return _comparator_gt

    else:
        if part1 == '<':
            # Less or equal
            return _comparator_le

        elif part1 == '>':
            # Greater or equal
            return _comparator_ge

        elif part1 == '~':
            # Approximate equality
            return _comparator_approximate


def _compute_operation(string, idx):
    """
    Tries to compute the LDAP operation at the given index

    Valid operations are :

    * & : AND
    * | : OR
    * ! : NOT

    :param string: A LDAP filter string
    :param idx: An index in the given string
    :return: The corresponding operator (AND, OR or NOT)
    """
    operator = string[idx]

    if operator == '&':
        return AND

    elif operator == '|':
        return OR

    elif operator == '!':
        return NOT

    return None


def _skip_spaces(string, idx):
    """
    Retrieves the next non-space character after idx index in the given string

    :param string: The string to look into
    :param idx: The base search index
    :return: The next non-space character index, -1 if not found
    """
    i = idx
    size = len(string)

    while i < size:
        if not string[i].isspace():
            return i

        i += 1

    return -1


def _parse_LDAP_criteria(ldap_filter, startidx=0, endidx=-1):
    """
    Parses an LDAP sub filter (criterion)

    :param ldap_filter: An LDAP filter string
    :param startidx: Sub-filter start index
    :param endidx: Sub-filter end index
    :return: The LDAP sub-filter
    :raise ValueError: Invalid sub-filter
    """
    comparators = "=<>~"

    if endidx < 0:
        endidx = len(ldap_filter)

    if startidx >= endidx or startidx < 0 or endidx > len(ldap_filter):
        raise ValueError("Invalid string range start={0}, end={1}" \
                         .format(startidx, endidx))

    # Get the comparator
    i = startidx
    escaped = False
    while i < endidx:
        if not escaped:
            if ldap_filter[i] == ESCAPE_CHARACTER:
                # Next character escaped
                escaped = True

            elif ldap_filter[i] in comparators:
                # Comparator found
                break

        else:
            # Escaped character ignored
            escaped = False

        i += 1

    else:
        # Comparator never found
        raise ValueError("Comparator not found in '{0}'" \
                         .format(ldap_filter[startidx:endidx]))

    if i == startidx:
        # Attribute name is missing
        raise ValueError("Attribute name is missing in '{0}'" \
                         .format(ldap_filter[startidx:endidx]))

    comparator = _compute_comparator(ldap_filter, i)
    if comparator is None:
        # Unknown comparator
        raise ValueError("Unknown comparator in '{0}' - {1}\nFilter : {2}" \
                         .format(ldap_filter[startidx:endidx], ldap_filter[i],
                                 ldap_filter))

    # The attribute name can be extracted directly
    attribute_name = ldap_filter[startidx:i].strip()

    # Find the end of the comparator
    i += 1
    if i >= endidx:
        raise ValueError("Compared value is missing in '{0}'" \
                         .format(ldap_filter[startidx:endidx]))

    while ldap_filter[i] in comparators:
        i += 1

    # Skip spaces
    i = _skip_spaces(ldap_filter, i)

    # Extract the value
    value = ldap_filter[i:endidx].strip()

    # Use the appropriate comparator if a joker is found in the filter value
    if value == '*':
        # Presence comparator
        comparator = _comparator_presence

    elif '*' in value:
        # Joker
        if comparator == _comparator_eq:
            comparator = _comparator_star

        elif comparator == _comparator_approximate:
            comparator = _comparator_approximate_star

    return LDAPCriteria(unescape_LDAP(attribute_name), unescape_LDAP(value),
                        comparator)


def _parse_LDAP(ldap_filter):
    """
    Parses the given LDAP filter string

    :param ldap_filter: An LDAP filter string
    :return: An LDAPFilter object, None if the filter was empty
    :raise ValueError: The LDAP filter string is invalid
    """
    if ldap_filter is None:
        # Nothing to do
        return None

    assert is_string(ldap_filter)

    # Remove surrounding spaces
    ldap_filter = ldap_filter.strip()
    if not ldap_filter:
        # Empty string
        return None

    escaped = False
    filter_len = len(ldap_filter)
    root = None
    stack = []
    subfilter_stack = []

    idx = 0
    while idx < filter_len:
        if not escaped:
            if ldap_filter[idx] == '(':
                # Opening filter : get the operator
                idx = _skip_spaces(ldap_filter, idx + 1)
                if idx == -1:
                    raise ValueError("Missing filter operator: {0}" \
                                     .format(ldap_filter))

                operator = _compute_operation(ldap_filter, idx)
                if operator is not None:
                    # New sub-filter
                    stack.append(LDAPFilter(operator))

                else:
                    # Sub-filter content
                    subfilter_stack.append(idx)

            elif ldap_filter[idx] == ')':
                # Ending filter : store it in its parent

                if len(subfilter_stack) != 0:
                    # criterion finished
                    startidx = subfilter_stack.pop()
                    criterion = _parse_LDAP_criteria(ldap_filter, startidx, idx)

                    if len(stack) != 0:
                        top = stack.pop()
                        top.append(criterion)
                        stack.append(top)
                    else:
                        # No parent : filter contains only one criterion
                        # Make a parent to stay homogeneous
                        root = LDAPFilter(AND)
                        root.append(criterion)

                elif len(stack) != 0:
                    # Sub filter finished
                    ended_filter = stack.pop()

                    if len(stack) != 0:
                        top = stack.pop()
                        top.append(ended_filter)
                        stack.append(top)

                    else:
                        # End of the parse
                        root = ended_filter

                else:
                    raise ValueError("Too many end of parenthesis:{0}: {1}" \
                                     .format(idx, ldap_filter[idx:]))

            elif ldap_filter[idx] == '\\':
                # Next character must be ignored
                escaped = True

        else:
            # Escaped character ignored
            escaped = False

        # Don't forget to increment...
        idx += 1

    # No root : invalid content
    if root is None:
        raise ValueError("Invalid filter string: {0}".format(ldap_filter))

    # Return the root of the filter
    return root.normalize()


def get_ldap_filter(ldap_filter):
    """
    Retrieves the LDAP filter object corresponding to the given filter.
    Parses it the argument if it is an LDAPFilter instance

    :param ldap_filter: An LDAP filter (LDAPFilter or string)
    :return: The corresponding filter, can be None
    :raise ValueError: Invalid filter string found
    :raise TypeError: Unknown filter type
    """
    if ldap_filter is None:
        return None

    if isinstance(ldap_filter, (LDAPFilter, LDAPCriteria)):
        # No conversion needed
        return ldap_filter

    elif is_string(ldap_filter):
        # Parse the filter
        return _parse_LDAP(ldap_filter)

    # Unknown type
    raise TypeError("Unhandled filter type {0}"\
                    .format(type(ldap_filter).__name__))


def combine_filters(filters, operator=AND):
    """
    Combines two LDAP filters, which can be strings or LDAPFilter objects

    :param filters: Filters to combine
    :param operator: The operator for combination
    :return: The combined filter, can be None if all filters are None
    :raise ValueError: Invalid filter string found
    :raise TypeError: Unknown filter type
    """
    if not filters:
        return None

    if not hasattr(filters, '__iter__') or is_string(filters):
        raise TypeError("Filters argument must be iterable")

    # Remove None filters and convert others
    ldap_filters = []
    for sub_filter in filters:
        if sub_filter is None:
            # Ignore None filters
            continue

        ldap_filter = get_ldap_filter(sub_filter)
        if ldap_filter is not None:
            # Valid filter
            ldap_filters.append(ldap_filter)

    if len(ldap_filters) == 0:
        # Do nothing
        return None

    elif len(ldap_filters) == 1:
        # Only one filter, return it
        return ldap_filters[0]

    new_filter = LDAPFilter(operator)

    for sub_filter in ldap_filters:
        # Direct combination
        new_filter.append(sub_filter)

    return new_filter.normalize()
