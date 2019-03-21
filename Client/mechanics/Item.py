from MapObject import MapObject


class Item(MapObject):
    def __init__(self, world, data, pos, is_used):
        MapObject.__init__(self, world, pos, image='images/' + data['item_id'] + '.png')
        self.item_id = data['item_id']
        self.title = data['title']
        self.gender = data['gender']
        self.min_level = data['min_level']
        self.item_pos = data['item_pos']
        self.is_used = is_used

    def draw_object(self):
        if self.is_used:
            self.world.draw(self.surface, [self.pos[0] + self.item_pos[0],
                                           self.pos[1] + self.item_pos[1]])
