<?php

namespace WPML\Support;

use Exception;
use WPML\Core\Component\MinimumRequirements\Application\Service\RequirementsService;

class Initializer {

	public static function getData(): array {
		global $wpml_dic;
		$requirementsService = $wpml_dic->make( RequirementsService::class );
		$invalidRequirements = $requirementsService->getInvalidRequirements();

		return[
			'showMinRequirementsComponent'  =>  count( $invalidRequirements ) > 0,
			'serializedInvalidRequirements' => self::serializeRequirements( $invalidRequirements )
		];
	}

	private static function serializeRequirements( $array ) {
		try {
			return esc_attr( (string) wp_json_encode( $array ) );
		} catch ( Exception $e ) {
			return '';
		}
	}
}
