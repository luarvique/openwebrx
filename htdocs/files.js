$.fn.fileTile = function() {
    this.each(function() {
        $(this).on('click', '.file-delete', function(e) {
            $.ajax("files/delete", {
                data: JSON.stringify({ name: this.value }),
                contentType: 'application/json',
                method: 'POST'
            }).done(function() {
                document.location.reload();
            });
            return false;
        });
    });
};

$(function(){
    $('.file-tile').fileTile();
});
