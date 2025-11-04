<?php

namespace WPML\Notices\SiteKey;

class Factory implements \IWPML_Backend_Action_Loader {
	public function create() {
		$notices = wpml_get_admin_notices();

		return new Notice( $notices );
	}
}
