// The following jQuery snippet will add a small square next to the selection
// drop-down on the `Add tag` page that will update to show the selected tag
// color as the drop-down value is changed.

django.jQuery(document).ready(function(){

  if (django.jQuery("#id_colour").length) {

    let colour;
    let colour_num;

    colour_num = django.jQuery("#id_colour").val() - 1;
    colour = django.jQuery('#id_colour')[0][colour_num].text;
    django.jQuery('#id_colour').after('<div class="colour_square"></div>');

    django.jQuery('.colour_square').css({
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
      django.jQuery('.colour_square').css({'background': colour});
    });

  } else if (django.jQuery("select[id*='colour']").length) {

    django.jQuery('select[id*="-colour"]').each(function (index, element) {
      let id;
      let loop_colour_num;
      let loop_colour;

      id = "colour_square_" + index;
      django.jQuery(element).after('<div class="colour_square" id="' + id + '"></div>');

      loop_colour_num = django.jQuery(element).val() - 1;
      loop_colour = django.jQuery(element)[0][loop_colour_num].text;

      django.jQuery("<style type='text/css'>\
                        .colour_square{ \
                            float: left; \
                            width: 20px; \
                            height: 20px; \
                            margin: 5px; \
                            border: 1px solid rgba(0,0,0,.2); \
                        } </style>").appendTo("head");
      django.jQuery('#' + id).css({'background': loop_colour});

      console.log(id, loop_colour_num, loop_colour);

      django.jQuery(element).change(function () {
        loop_colour_num = django.jQuery(element).val() - 1;
        loop_colour = django.jQuery(element)[0][loop_colour_num].text;
        django.jQuery('#' + id).css({'background': loop_colour});
        console.log('#' + id, loop_colour)
      });
    })

  }

});
