#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ast import Pass
import sys
import itertools
import copy
from collections import Counter

from ...action import Action, PlayAction, DiscardAction, ClueAction
from ...card import Card, CardAppearance, get_appearance
from ...deck import DECKS
from ...base_strategy import BaseStrategy
from .clues_manager import CluesManager
import random




class Knowledge:
    """
    An instance of this class represents 
    - What a player knows about a card, as known by everyone in self.color and self.number
    """
    
    def __init__(self, color=None, number=None):
        self.color: str = color                  # know exact color, CARD.COLOR enum
        self.number: int = number                # know exact number, int
        self.implicit_colors = []
        self.implicit_numbers = []
        self.playable: bool = False               # at some point, this card was playable
        self.non_playable: bool = False           # at some point, this card was not playable
        self.useless: bool = False                # this card is useless    
    
    def __repr__(self):
        print
        return ("C" if self.color else "-") + ("N" if self.number else "-") + ("P" if self.playable else "-") + ("Q" if self.non_playable else "-") + ("L" if self.useless else "-")
    
    
    def knows(self, clue_type):
        """
        Does the player know the color/number?
        """
        assert clue_type in Action.CLUE_TYPES
        if clue_type == Action.COLOR:
            return self.color
        else:
            return self.number
    
    def knows_exactly(self):
        """
        Does the player know exactly this card?
        """
        return self.color and (self.number or self.playable)


class Strategy(BaseStrategy):
    """
    An instance of this class represents a player's strategy.
    It only has the knowledge of that player, and it must make decisions.
    """
    
    DECK_SIZE_BEFORE_FULL_SEARCH = {
        4: 10,
        5: 4,
    }   # k (number of cards per hand): size of the deck when we want to consider all combinations of cards
    
    
    def __init__(self, verbose=False, params={}):
        self.COLORS_TO_NUMBERS = {color: i for (i, color) in enumerate(Card.COLORS)}
        self.verbose = verbose
        self.params = params
    
    
    def initialize(self, id, num_players, k, board, deck_type, my_hand, hands, discard_pile, deck_size, game):
        """
        To be called once before the beginning.
        """
        self.id = id
        self.num_players = num_players
        self.k = k  # number of cards per hand
        self.board = board
        self.deck_type = deck_type
        
        # store a copy of the full deck
        self.full_deck = get_appearance(DECKS[deck_type]())
        self.full_deck_composition = Counter(self.full_deck)
        
        # hands
        self.my_hand = my_hand  # says in which positions there is actually a card
        self.hands = hands
        
        # discard pile
        self.discard_pile = discard_pile
        
        # deck size
        self.deck_size = deck_size
        
        # for each of my card, store its possibilities using both implicit and explicit information
        self.possibilities = [Counter(self.full_deck) for i in range(self.k)]
        
        # remove cards of other players from possibilities
        self.update_possibilities()
        
        # knowledge of all players
        self.knowledge = [[Knowledge(color=False, number=False) for j in range(k)] for i in range(num_players)]
        
        self.clues_manager = CluesManager(self)   

        self.game = game 
    

    def visible_cards(self):
        """
        Counter of all the cards visible by me.
        """
        res = Counter(self.discard_pile)
        for hand in self.hands.values():
            res += Counter(hand)
        
        return res
    
    
    def update_possibilities(self):
        """
        Update possibilities removing visible cards.
        """
        visible_cards = self.visible_cards()
        for p in self.possibilities:
            for card in self.full_deck_composition:
                if card in p:
                    # this card is still possible
                    # update the number of possible occurrences
                    p[card] = self.full_deck_composition[card] - visible_cards[card]
                    
                    if p[card] == 0:
                        # remove this card
                        del p[card]
        
        # TODO: why does this not work?
        # assert all(sum(p.values()) > 0 or self.my_hand[card_pos] is None for (card_pos, p) in enumerate(self.possibilities))    # check to have at least one possible card!
    
    
    def update_possibilities_with_combinations(self):
        """
        Update possibilities examining all combinations of my hand.
        Better to do it with only few cards remaining!
        """
        possible_cards = Counter()
        for p in self.possibilities:
            assert all(x > 0 for x in list(p.values()))
            possible_cards |= p
        
        new_possibilities = [set() for card_pos in range(self.k)]
        
        num_cards = len([x for x in self.my_hand if x is not None])
        assert num_cards <= self.k
        
        # cycle over all combinations
        for comb in itertools.permutations(list(possible_cards.elements()), num_cards):
            # construct hand
            hand = copy.copy(self.my_hand)
            i = 0
            for card_pos in range(self.k):
                if hand[card_pos] is not None:
                    hand[card_pos] = comb[i]
                    i += 1
            
            # check if this hand is possible
            if all(card is None or self.possibilities[card_pos][card] > 0 for (card_pos, card) in enumerate(hand)):
                # this hand is possible
                # self.log("possible hand %r" % hand)
                
                for (card_pos, card) in enumerate(hand):
                    if card is not None:
                        new_possibilities[card_pos].add(card)
        
        self.log("old possibilities %r" % [len(p) for p in self.possibilities])
        self.log("new possibilities %r" % [len(p) for p in new_possibilities])
        
        # update possibilities
        for (card_pos, p) in enumerate(self.possibilities):
            self.possibilities[card_pos] = p & Counter(new_possibilities[card_pos])
        
        self.update_possibilities() # set the right multiplicities
    
    
    def next_player_id(self):
        return (self.id + 1) % self.num_players
    

    def other_players_id(self):
        return [i for i in range(self.num_players) if i != self.id]
    

    def finesse_index(self, player_id) -> int:
        """
        Returns the index of the leftmost unclued(finesse) card of the given player.
        """

        "*** BEGIN SOLUTION ***"
        for i, kn in enumerate(self.knowledge[player_id]):
            if not (kn.knows(Action.COLOR) or kn.knows(Action.NUMBER)):
                return i
        "*** END SOLUTION ***"


    def chop_index(self, player_id) -> int:
        """
        Returns the index of the rightmost unclued(chop) card of the given player.
        """

        "*** BEGIN SOLUTION ***"
        for i, kn in enumerate(self.knowledge[player_id][::-1]):
            if not (kn.knows(Action.COLOR) or kn.knows(Action.NUMBER)):
                return (self.k - 1) - i
        return None
        "*** END SOLUTION ***"


    def focus_index(self, clue_action: ClueAction):
        """
        Returns the focus index of a clue that touches all cards in card_pos
        """

        chop_idx = self.chop_index(clue_action.target_id) if clue_action.former_chop is None else clue_action.former_chop
        focus_idx = chop_idx if chop_idx in clue_action.cards_pos else clue_action.cards_pos[0]
        return focus_idx


    def update_knowledge(self, player_id, card_pos, new_card_exists):
        self.knowledge[player_id].pop(card_pos)
        self.knowledge[player_id].insert(0, Knowledge(None, None))
    
    
    def print_knowledge(self):
        print("Knowledge")
        for i in range(self.num_players):
            print("Player %d:" % i, end=' ')
            for card_pos in range(self.k):
                print(self.knowledge[i][card_pos], end=' ')
            print()
        print()

    
    def feed_turn(self, player_id: int, action: Action):
        """
        Receive information about a played turn.
        """
        if action.type in [Action.PLAY, Action.DISCARD]:
            # reset knowledge of the player
            new_card = self.my_hand[0] if player_id == self.id else self.hands[player_id][0]
            self.update_knowledge(player_id, action.card_pos, new_card is not None)
            
            if player_id == self.id:
                # check for my new card
                self.possibilities.pop(action.card_pos)
                self.possibilities.insert(0, Counter(self.full_deck) if self.my_hand[0] is not None else Counter())
        
        elif action.type == Action.CLUE:
            # someone gave a clue!
            self.clues_manager.receive_clue(player_id, action)
        
        # update possibilities with visible cards
        self.update_possibilities()

        if action.type == Action.CLUE:
            self.infer_clue_intent(player_id, action)
        
        # print knowledge
        if self.verbose and self.id == self.num_players-1:
            self.print_knowledge()
    

    def infer_clue_intent(self, clue_giver_id: int, clue_action: ClueAction):
        focus_idx = self.focus_index(clue_action)
        card_possibilities = self.possibilities[focus_idx]
        kn = self.knowledge[clue_action.target_id][focus_idx]
        if clue_action.clue_type == ClueAction.COLOR:
            # Color Clue
            # Infer immediate play
            inferred_number = self.board[clue_action.color] + 1

            # Delete other possibilities
            for card in copy.copy(card_possibilities):
                if card.number != inferred_number:
                    del card_possibilities[card]
            kn.implicit_numbers.append(inferred_number)
            kn.playable = True
        else:
            # Number clue
            former_chop_idx = clue_action.former_chop
            if former_chop_idx and former_chop_idx in clue_action.cards_pos:
                # It was a save clue
                return

            # Else, it was a play clue
            inferred_colors = [color for color, number in self.board.items() if clue_action.number == number + 1]
            
            for card in copy.copy(card_possibilities):
                if card.color not in inferred_colors:
                    del card_possibilities[card]
            kn.implicit_numbers.extend(inferred_colors)
            kn.playable = True
        

        

    def get_best_discard(self):
        """
        Choose the best card to be discarded.
        """
        return NotImplementedError
    
    
    def get_play_clues(self):
        """
        Choose the best play clue to give. TODO: Currently random choice.
        """
        play_clues = []
        for target_id in self.other_players_id():
            for card_pos in range(self.k):
                    card = self.hands[target_id][card_pos]
                    kn = self.knowledge[target_id][card_pos]
                    if card and card.playable(self.board):
                        chop_idx = self.chop_index(target_id)
                        color_clue = ClueAction(target_id, color=card.color)
                        color_clue.apply(self.game)
                        color_clue.former_chop = chop_idx

                        number_clue = ClueAction(target_id, number=card.number)
                        number_clue.apply(self.game)
                        number_clue.former_chop = chop_idx

                        if self.check_focus_match(color_clue, card_pos) and not kn.knows(ClueAction.COLOR) and self.is_good_touch(color_clue):
                            play_clues.append(color_clue)
                        elif self.check_focus_match(number_clue, card_pos) and not kn.knows(ClueAction.NUMBER) and self.is_good_touch(number_clue):
                            play_clues.append(number_clue)
                
            
        return play_clues


    def get_best_play_last_round(self):
        """
        Choose the best card to play in the last round of the game.
        The players know almost everything, and it is reasonable to examine all the possibilities.
        """
        return NotImplementedError

    
    def check_focus_match(self, clue_action: ClueAction, intended_focus: int):
        """
        Checks if we give a clue, the inferred focus will be the same as the intended focus
        """
        return self.focus_index(clue_action) == intended_focus


    def is_good_touch(self, clue_action: ClueAction):
        """
        Checks hands of all other players to see if a clue_action's card target has already been touched.
        If so, returns True.
        """
        # Check within hand
        # if self.for card_pos in clue_action.card_pos

        # Check other hands
        for card_pos in clue_action.cards_pos:
            card = self.hands[clue_action.target_id][card_pos]
            for player_id in range(self.num_players):
                if player_id != clue_action.target_id and player_id != self.id:
                    for card_pos, kn in enumerate(self.knowledge[player_id]):
                        other_card = self.hands[player_id][card_pos]
                        if card and other_card and card.equals(other_card) and (kn.knows(ClueAction.COLOR) or kn.knows(ClueAction.NUMBER)):
                            return False
        return True


    def get_turn_action(self):
        """
        Choose action for this turn.
        """

        # If you see a critical card on someone's chop_index, save clue it. Clue the earliest person in play order
        if self.game.clues > 0:
            target_id = self.next_player_id()
            while target_id != self.id:
                for card_pos in range(self.k):
                    card = self.hands[target_id][card_pos]
                    chop_idx = self.chop_index(target_id)
                    if card and card_pos == chop_idx and card.critical(self.board, self.full_deck, self.discard_pile):
                        if card.number == 5 or card.number == 2:
                            clue_action = ClueAction(target_id, number=card.number)
                            clue_action.apply(self.game)
                            clue_action.former_chop = chop_idx
                            return clue_action
                target_id = (target_id + 1) % self.num_players

        # If have something playable in hand, play it. 
        my_hand_kn = self.knowledge[self.id]
    
        for (card_pos, kn) in enumerate(my_hand_kn):
            if kn.playable:
                return PlayAction(card_pos)
                

        # Otherwise, try to give a play clue if there are clues left.
        if self.game.clues > 0:
            play_clues = self.get_play_clues()
            if len(play_clues) > 0:
                return random.choice(play_clues)

        # Otherwise, discard a useless card that you know exactly
        for card_pos, kn in enumerate(self.knowledge[self.id]):
            if kn.knows_exactly():
                card = CardAppearance(kn.color, kn.number)
                if not card.useful(self.board, self.full_deck, self.discard_pile):
                    return DiscardAction(card_pos)

        # Otherwise, discard chop
        chop_idx = self.chop_index(self.id)
        if chop_idx:
            # Discard chop card
            return DiscardAction(chop_idx)
        return DiscardAction(0)
       




        








