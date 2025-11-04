<?php

namespace WPML\TM\Troubleshooting;

use WPML\UserInterface\Web\Core\Component\Troubleshooting\Application\TroubleshootingController;

class PostHogRecording implements \IWPML_Backend_Action {

	public function add_hooks() {
		add_action( 'after_setup_complete_troubleshooting_functions', [ $this, 'renderContainer' ], 12 );
	}

	public function renderContainer() {
		TroubleshootingController::render();
	}

}
