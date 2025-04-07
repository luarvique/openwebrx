$.fn.bookmarkDialog = function() {
    var $el = this;
    return {
        setModes: function(modes) {
            $el.find('#modulation').html(modes.map(function(m) {
                return '<option value="' + m.modulation + '">' + m.name + '</option>';
            }).join(''));
            return this;
        },
        setUnderlying: function(modes) {
            $el.find('#underlying').html('<option value="">None</option>' +
            modes.filter(function(m) {
                return !m.underlying && m.type === 'analog';
            }).map(function(m) {
                return '<option value="' + m.modulation + '">' + m.name + '</option>';
            }).join(''));
            return this;
        },
        setValues: function(bookmark) {
            var $form = $el.find('form');
            ['name', 'frequency', 'modulation', 'underlying', 'description', 'scannable'].forEach(function(key) {
                var $input = $form.find('#' + key);
                if ($input.is(':checkbox')) {
                    $input.prop('checked', bookmark[key]);
                } else {
                    $input.val(bookmark[key]);
                }
            });
            $el.data('id', bookmark.id || false);
            return this;
        },
        getValues: function() {
            var bookmark = {};
            var valid = true;
            ['name', 'frequency', 'modulation', 'underlying', 'description', 'scannable'].forEach(function(key) {
                var $input = $el.find('#' + key);
                valid = valid && $input[0].checkValidity();
                bookmark[key] = $input.is(':checkbox')? $input.is(':checked') : $input.val();
            });
            if (!valid) {
                $el.find("form :submit").click();
                return;
            }
            bookmark.id = $el.data('id');
            return bookmark;
        }
    }
};
