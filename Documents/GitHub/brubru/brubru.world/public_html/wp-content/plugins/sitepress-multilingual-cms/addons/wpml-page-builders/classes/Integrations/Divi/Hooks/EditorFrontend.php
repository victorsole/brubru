<?php

namespace WPML\Compatibility\Divi\Hooks;

use WPML\FP\Fns;
use WPML\LIB\WP\Hooks;

class EditorFrontend implements \IWPML_Frontend_Action {

	public function add_hooks() {
		if ( function_exists( 'et_core_is_fb_enabled' ) ) {
			Hooks::onAction( 'et_builder_ready' )
			     ->then( Fns::tap( [ $this, 'maybeDisplayModalPageBuilderWarning' ] ) );
		}
	}

	public function maybeDisplayModalPageBuilderWarning() {
		if ( is_user_logged_in() && function_exists( 'et_core_is_fb_enabled' ) && et_core_is_fb_enabled() && get_the_ID() ) {
			$diviArgs = [
				'iframeModeQuerySelector' => 'html.et-fb-app-frame',
			];
			do_action( 'wpml_maybe_display_modal_page_builder_warning', get_the_ID(), 'Divi Builder', $diviArgs );
		}
	}
}
