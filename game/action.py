#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Action(object):
    """
    Generic action.
    """
    PLAY = 'Play'
    DISCARD = 'Discard'
    CLUE = 'Clue'
    
    COLOR = 'C'
    NUMBER = 'N'
    
    TYPES = [PLAY, DISCARD, CLUE]
    CLUE_TYPES = [COLOR, NUMBER]
    
    
    def __init__(self, type, card_pos: int = None, player_id: int = None, color=None, number=None):
        raise NotImplementedError
    
    def apply(self, game):
        # populate other fields, using information from the game
        self.turn = game.get_current_turn()


class PlayAction(Action):
    """
    Action of type PLAY.
    """
    def __init__(self, card_pos):
        self.type = self.PLAY
        self.card_pos = card_pos
    
    def __repr__(self):
        return "Play card %d" % self.card_pos


class DiscardAction(Action):
    """
    Action of type DISCARD.
    """
    def __init__(self, card_pos):
        self.type = self.DISCARD
        self.card_pos = card_pos
    
    def __repr__(self):
        return "Discard card %d" % self.card_pos


class ClueAction(Action):
    """
    Action of type CLUE.
    """
    def __init__(self, target_id, color=None, number=None, clue_type=None, value=None):
        """
        A ClueAction can be constructed giving the color or the number, or giving the clue type and the value.
        """
        self.type = self.CLUE
        self.target_id = target_id
        
        if color is not None or number is not None:
            assert color is not None and number is None or color is None and number is not None
            assert clue_type is None and value is None
            self.color = color
            self.number = number
            self.value = color if color is not None else number
            self.clue_type = self.COLOR if color is not None else self.NUMBER
        else:
            assert clue_type is not None and value is not None
            assert clue_type in self.CLUE_TYPES
            self.clue_type = clue_type
            self.value = value
            if clue_type == Action.COLOR:
                self.color = value
                self.number = None
            else:
                self.color = None
                self.number = value
    
    
    def __repr__(self):
        return "Clue to player %d about %r" % (self.player_id, self.value)
    
    def apply(self, game):
        # populate other fields, using information from the game
        super(ClueAction, self).apply(game)
        
        player = game.players[self.target_id]
        self.cards_pos = [i for (i, card) in enumerate(player.hand) if card is not None and (card.number == self.number or card.color == self.color)]
        assert len(self.cards_pos) > 0


