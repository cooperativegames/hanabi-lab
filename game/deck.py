#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .card import Card
from typing import List


def standard_deck() -> List[Card]:
    deck = []
    id = 0
    for color in Card.COLORS:
        for number in range(1, Card.NUM_NUMBERS + 1):
            if number == 1:
                quantity = 3
            elif 2 <= number <= 4:
                quantity = 2
            elif number == 5:
                quantity = 1
            else:
                raise Exception("Unknown card parameters.")
            
            for i in range(quantity):
                deck.append(Card(id, color, number))
                id += 1
    
    assert len(deck) == 50
        
    return deck


def standard_deck_25() -> List[Card]:
    return standard_deck()


DECK50 = 'deck50'

DECKS = {
    DECK50: standard_deck_25
}

