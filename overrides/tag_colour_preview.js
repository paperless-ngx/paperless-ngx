// The following jQuery snippet will add a small square next to the selection
// drop-down on the `Add tag` page that will update to show the selected tag
// color as the drop-down value is changed. Copy and paste it into
// ``PAPERLESS_MEDIADIR/overrides.js`` to see the effects.

let colour;
let colour_num;

colour_num = django.jQuery("#id_colour").val() - 1;
colour = django.jQuery('#id_colour')[0][colour_num].text;
django.jQuery('#id_colour').after('<div id="colour_square"></div>')

django.jQuery('#colour_square').css({
    'float': 'left',
    'width': '20px',
    'height': '20px',
    'margin': '5px',
    'border': '1px solid rgba(0, 0, 0, .2)',
    'background': colour
});

django.jQuery('#id_colour').change(function () {
    colour_num = django.jQuery("#id_colour").val() - 1;
    colour = django.jQuery('#id_colour')[0][colour_num].text;
    django.jQuery('#colour_square').css({'background': colour});
});
