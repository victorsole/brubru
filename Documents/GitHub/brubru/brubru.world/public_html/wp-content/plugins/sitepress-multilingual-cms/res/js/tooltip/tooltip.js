var WPMLCore = WPMLCore || {};

WPMLCore.Tooltip = function (element) {
	this.trigger = element;
	this.content = this.trigger.html(this.trigger.html()).text();
	this.edge = 'bottom';
	this.align = 'left';
	this.margin_left = '-54px';

	if (!this.content) {
		this.content = this.decodeEntities(this.trigger.data('content'));
	}

	if (this.trigger.data('edge')) {
		this.edge = this.trigger.data('edge');
	}

	if (this.trigger.data('align')) {
		this.align = this.trigger.data('align');
	}

	if (this.trigger.data('margin_left')) {
		this.margin_left = this.trigger.data('margin_left');
	}

	this.trigger.empty();
	this.trigger.click(jQuery.proxy(this.onTriggerClick, this));
};

WPMLCore.Tooltip.prototype = {
	open:           function () {
		if (this.trigger.length && this.content) {
			this.trigger.addClass('js-wpml-active-tooltip');
			this.trigger.pointer({
														 pointerClass: 'js-wpml-tooltip',
														 content:      this.content,
														 position:     {
															 edge:  this.edge,
															 align: this.align
														 },
														 show:         jQuery.proxy(this.onShow, this),
														 close:        this.onClose,
														 buttons:      this.buttons

													 }).pointer('open');
		}
	},
	onShow:         function (event, t) {
		t.pointer.css('marginLeft', this.margin_left);
	},
	onClose:        function (event, t) {
		t.pointer.css('marginLeft', '0');
	},
	onTriggerClick: function (e) {
		e.preventDefault();
		this.open();
	},
	buttons:        function (event, t) {
		var button = jQuery('<a class="close" href="#">&nbsp;</a>');

		return button.on('click.pointer', function (e) {
			e.preventDefault();
			t.element.pointer('close');
		});
	},
	decodeEntities: function (encodedString) {
		var textArea = document.createElement('textarea');
		textArea.innerHTML = encodedString;
		return textArea.value;
	}
};

WPMLCore.initializeTooltips = function() {
	"use strict";

	var tooltips = jQuery('.js-wpml-tooltip-open'), tooltip = {};

	tooltips.each(function (index, element) {
		tooltip = new WPMLCore.Tooltip(jQuery(element));
	});

  var hoverableTooltips = jQuery('.js-wpml-hoverable-tooltip');
  hoverableTooltips.each(function (index, element) {
    createHoverableTooltip(jQuery(element));
  });
};

(function () {
    'use strict';

    jQuery(function () {
        WPMLCore.initializeTooltips();
    });
}());

function createHoverableTooltip(triggerEl) {
  var isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0 || navigator.msMaxTouchPoints > 0;

  if (isTouchDevice) {
    return;
  }

  var closeTimeout;
  triggerEl.on('mouseenter', function() {
    if (typeof closeTimeout === "number") {
      clearTimeout(closeTimeout);
    }
    openTooltip(jQuery(this));
  });

  triggerEl.on('mouseleave', function() {
    clearTimeout(closeTimeout);
    closeTimeout = setTimeout(function(event) {
      triggerEl.pointer('close');
    }, 500);
  });

  function openTooltip(triggerNode) {
    var content = triggerNode.data('content');
    var link_text = triggerNode.data('link-text');
    var link_url = triggerNode.data('link-url');
    var link_target = triggerNode.data('link-target');

    if (link_text && link_text.length > 0) {
      var content_link_target = 'target="' + link_target + '"';
      content += '<br><a href="' + link_url + '" ' + content_link_target + '>';
      content += link_text;
      content += '</a>';
    }

    clearTimeout(closeTimeout);
    jQuery('.js-wpml-hoverable-tooltip-active').pointer('close');

    if(triggerNode.length && content) {
      var pointerClass = 'js-wpml-hoverable-tooltip wpml-hoverable-tooltip';
      triggerNode.addClass('js-wpml-hoverable-tooltip-active');
      if (triggerNode.hasClass('js-wpml-hoverable-tooltip-wide')) {
        pointerClass += ' wide-tooltip';
      }
      triggerNode.pointer({
        pointerClass : pointerClass,
        content:       content,
        position: {
          my: 'center bottom',
          at: 'center top',
          edge: 'bottom center',
        },
        show: function(event, t){
          jQuery(t.pointer).on('mouseenter', function() {
            clearTimeout(closeTimeout);
          });
          jQuery(t.pointer).on('mouseleave', function() {
            clearTimeout(closeTimeout);
            triggerEl.pointer('close');
          });
        },
        close: function(event, t){
          jQuery(t.pointer).off('mouseenter');
          jQuery(t.pointer).off('mouseleave');
        },
        buttons: function() {},
      }).pointer('open');
    }
  }
}