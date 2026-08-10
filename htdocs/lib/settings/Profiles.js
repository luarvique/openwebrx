$.fn.profiles = function() {
    this.each(function() {
        $(this).on('click', '.move-down', function(e) {
            location.replace(document.URL.replace(/(\/sdr\/[^\/]+)\/profile\/([^\/]+)$/, '$1/moveprofiledown/$2'));
            return false;
        });

        $(this).on('click', '.move-up', function(e) {
            location.replace(document.URL.replace(/(\/sdr\/[^\/]+)\/profile\/([^\/]+)$/, '$1/moveprofileup/$2'));
            return false;
        });

        $(this).on('click', '.clone', function(e) {
            location.replace(document.URL.replace(/(\/sdr\/[^\/]+)\/profile\/([^\/]+)$/, '$1/newprofile/$2'));
            return false;
        });
    });
}
