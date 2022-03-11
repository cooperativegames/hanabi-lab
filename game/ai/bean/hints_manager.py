#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import itertools
import copy

from ...action import Action, PlayAction, DiscardAction, HintAction
from ...card import Card


class BaseHintsManager(object):
    """
    Base class for a HintsManager.
    """
    def __init__(self, strategy):
        self.strategy = strategy    # my strategy object
        
        # copy something from the strategy
        self.id = strategy.id
        self.num_players = strategy.num_players
        self.k = strategy.k
        self.possibilities = strategy.possibilities
        self.full_deck = strategy.full_deck
        self.board = strategy.board
        self.knowledge = strategy.knowledge
        
        self.COLORS_TO_NUMBERS = {color: i for (i, color) in enumerate(Card.COLORS)}
    
    
    def log(self, message):
        self.strategy.log(message)
    
    
    def is_duplicate(self, card):
        """
        Says if the given card is owned by some player who knows everything about it.
        """
        # check other players' hands
        for (player_id, hand) in self.strategy.hands.items():
            for card_pos in range(self.k):
                kn = self.knowledge[player_id][card_pos]
                if kn.knows_exactly() and hand[card_pos] is not None and hand[card_pos].equals(card):
                    return True
        
        # check my hand
        for card_pos in range(self.k):
            kn = self.knowledge[self.id][card_pos]
            if kn.knows_exactly() and any(card.equals(c) for c in self.strategy.possibilities[card_pos]):
                return True
        
        return False
    
    
    def is_usable(self, hinter_id):
        """
        Check that it is possible to pass all the information.
        """
        return True
    
    
    def receive_hint(self, player_id, action):
        """
        Receive hint given by player_id and update knowledge.
        """
        if action.player_id == self.id:
            # process direct hint
            for (i, p) in enumerate(self.possibilities):
                for card in self.strategy.full_deck_composition:
                    if not card.matches_hint(action, i) and card in p:
                        # self.log("removing card %r from position %d due to hint" % (card, i))
                        # p.remove(card)
                        del p[card]
        
        # update knowledge
        for card_pos in action.cards_pos:
            kn = self.knowledge[action.player_id][card_pos]
            if action.hint_type == Action.COLOR:
                kn.color = True
            else:
                kn.number = True
        
        assert self.possibilities is self.strategy.possibilities
        assert self.board is self.strategy.board
        assert self.knowledge is self.strategy.knowledge
    
    
    def get_hint(self):
        """
        Compute hint to give.
        """
        raise NotImplementedError
    

class ValueHintsManager(BaseHintsManager):
    """
    Value hints manager.
    A hint communicates to every other player the value (color or number) of one of his cards.
    
    More specifically, the players agree on a function player->card_pos (which depends on the turn and on other things).
    The current player computes the sum of the values (color or number) of the agreed cards,
    and gives a hint on that value.
    Then each of the other players deduces the value of his card.
    """
    
    def __init__(self, *args, **kwargs):
        super(ValueHintsManager, self).__init__(*args, **kwargs)
        self.COLORS_TO_NUMBERS = {color: i for (i, color) in enumerate(Card.COLORS)}
    
    
    def shift(self, turn):
        # a variable shift in the hint
        return turn + turn / self.num_players
    
    
    def choose_card(self, player_id, target_id, turn, hint_type):
        """
        Choose which of the target's cards receive a hint from the current player in the given turn.
        """
        hand = self.strategy.my_hand if target_id == self.id else self.strategy.hands[target_id]
        possible_cards = [card_pos for (card_pos, kn) in enumerate(self.knowledge[target_id]) if hand[card_pos] is not None and not (kn.color if hint_type == Action.COLOR else kn.number)]
        
        if len(possible_cards) == 0:
            # do not give hints
            return None
        
        # TODO: forse usare un vero hash
        n = turn * 11**3 + (0 if hint_type == Action.COLOR else 1) * 119 + player_id * 11 + target_id
        
        return possible_cards[n % len(possible_cards)]
    
    
    def choose_all_cards(self, player_id, turn, hint_type):
        """
        Choose all cards that receive hints (of the given type) from the given player in the given turn.
        """
        return {target_id: self.choose_card(player_id, target_id, turn, hint_type) for target_id in range(self.num_players) if target_id != player_id and self.choose_card(player_id, target_id, turn, hint_type) is not None}
    
    
    def infer_playable_cards(self, player_id, action):
        """
        From the choice made by the hinter (give hint on color or number), infer something
        about the playability of my cards.
        Here it is important that:
        - playability of a card depends only on things that everyone sees;
        - the choice of the type of hint (color/number) is primarily based on the number of playable cards.
        Call this function before decode_hint(), i.e. before knowledge is updated.
        """
        hint_type = action.hint_type
        opposite_hint_type = Action.NUMBER if hint_type == Action.COLOR else Action.COLOR
        
        cards_pos = self.choose_all_cards(player_id, action.turn, hint_type)
        alternative_cards_pos = self.choose_all_cards(player_id, action.turn, opposite_hint_type)
        
        if self.id not in cards_pos or self.id not in alternative_cards_pos:
            # I already knew about one of the two cards
            return None

        if action.player_id == self.id:
            # the hint was given to me, so I haven't enough information to infer something
            return None
        
        if hint_type == Action.NUMBER:
            # the alternative hint would have been on colors
            visible_colors = set(card.color for (i, hand) in self.strategy.hands.items() for card in hand if i != player_id and card is not None)   # numbers visible by me and by the hinter
            if len(visible_colors) < Card.NUM_COLORS:
                # maybe the hinter was forced to make his choice because the color he wanted was not available
                return None
            
        else:
        # the alternative hint would have been on numbers
            visible_numbers = set(card.number for (i, hand) in self.strategy.hands.items() for card in hand if i != player_id and card is not None)   # numbers visible by me and by the hinter
            if len(visible_numbers) < Card.NUM_NUMBERS:
                # maybe the hinter was forced to make his choice because the number he wanted was not available
                return None
        
        
        involved_cards = [hand[cards_pos[i]] for (i, hand) in self.strategy.hands.items() if i != player_id and i in cards_pos] + [self.strategy.hands[action.player_id][card_pos] for card_pos in action.cards_pos if (action.player_id not in cards_pos or card_pos != cards_pos[action.player_id])]
        
        my_card_pos = cards_pos[self.id]
        num_playable = sum(1 for card in involved_cards if card.playable(self.strategy.board) and not self.is_duplicate(card))
        
        alternative_involved_cards = [hand[alternative_cards_pos[i]] for (i, hand) in self.strategy.hands.items() if i != player_id and i in alternative_cards_pos]
        alternative_my_card_pos = alternative_cards_pos[self.id]
        alternative_num_playable = sum(1 for card in alternative_involved_cards if card.playable(self.strategy.board) and not self.is_duplicate(card))
        
        # self.log("Num playable: %d, %d" % (num_playable, alternative_num_playable))
        # self.log("%r %r" % (involved_cards, my_card_pos))
        # self.log("%r %r" % (alternative_involved_cards, alternative_my_card_pos))
        
        if alternative_num_playable > num_playable:
            assert alternative_num_playable == num_playable + 1
            # found a playable card and a non-playable card!
            self.log("found playable card (%d) and non-playable card (%d)" % (my_card_pos, alternative_my_card_pos))
            return my_card_pos, alternative_my_card_pos
        
        

    def decode_hint(self, player_id, action):
        """
        Decode hint given by someone else (not necessarily directly to me).
        """
        hint_type = action.hint_type
        cards_pos = self.choose_all_cards(player_id, action.turn, hint_type)
        # self.log("%r" % cards_pos)
        
        # update knowledge
        for (target_id, card_pos) in cards_pos.items():
            kn = self.knowledge[target_id][card_pos]
            if hint_type == Action.COLOR:
                kn.color = True
            else:
                kn.number = True
        
        # decode my hint
        if self.id in cards_pos:
            n = action.number if hint_type == Action.NUMBER else self.COLORS_TO_NUMBERS[action.color]
            my_card_pos = cards_pos[self.id]
            modulo = Card.NUM_NUMBERS if hint_type == Action.NUMBER else Card.NUM_COLORS
            
            involved_cards = [hand[cards_pos[i]] for (i, hand) in self.strategy.hands.items() if i != player_id and i in cards_pos]
            
            m = sum(card.number if hint_type == Action.NUMBER else self.COLORS_TO_NUMBERS[card.color] for card in involved_cards) + self.shift(action.turn)
            my_value = (n - m) % modulo
            
            # self.log("involved_cards: %r" % involved_cards)
            # self.log("m: %d, my value: %d, shift: %d" % (m, my_value,self.shift(action.turn)))
            
            number = my_value if hint_type == Action.NUMBER else None
            if number == 0:
                number = 5
            color = Card.COLORS[my_value] if hint_type == Action.COLOR else None
            
            return my_card_pos, color, number
        
        else:
            # no hint (apparently I already know everything)
            return None
    
    
    
    def receive_hint(self, player_id, action):
        """
        Receive hint given by player_id and update knowledge.
        """
        # maybe I wasn't given a hint because I didn't have the right cards
        # recall: the hint is given to the first suitable person after the one who gives the hint
        for i in list(range(player_id + 1, self.num_players)) + list(range(player_id)):
            if i == action.player_id:
                # reached hinted player
                break
            
            elif i == self.id:
                # I was reached first!
                # I am between the hinter and the hinted player!
                for (i, p) in enumerate(self.possibilities):
                    for card in self.full_deck:
                        if not card.matches_hint(action, -1) and card in p:
                            # self.log("removing card %r from position %d due to hint skip" % (card, i))
                            del p[card]
        
        # infer playability of some cards, from the type of the given hint
        res = self.infer_playable_cards(player_id, action)
        
        if res is not None:
            # found a playable and a non-playable card
            playable, non_playable = res
            for card in self.full_deck:
                if card.playable(self.board) and card in self.possibilities[non_playable] and not self.is_duplicate(card):
                    # self.log("removing %r from position %d" % (card, non_playable))
                    del self.possibilities[non_playable][card]
                elif not card.playable(self.board) and card in self.possibilities[playable] and not self.is_duplicate(card):
                    # self.log("removing %r from position %d" % (card, playable))
                    del self.possibilities[playable][card]
        
        # process value hint
        res = self.decode_hint(player_id, action)
        
        if res is not None:
            card_pos, color, number = res
            # self.log("thanks to indirect hint, understood that card %d has " % card_pos + ("number %d" % number if action.hint_type == Action.NUMBER else "color %s" % color))
        
            p = self.possibilities[card_pos]
            for card in self.full_deck:
                if not card.matches(color=color, number=number) and card in p:
                    del p[card]
        
        # important: this is done at the end because it changes the knowledge
        super(ValueHintsManager, self).receive_hint(player_id, action)
    
    
    def compute_hint_value(self, turn, hint_type):
        """
        Returns the color/number we need to give a hint about.
        """
        return NotImplementedError
    
    
    def get_hint(self):
        """
        Choose the best hint to give, if any.
        """
        return NotImplementedError
