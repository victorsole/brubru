<?php

namespace WPML\MediaTranslation;

class MediaField {

	/**
	 * Regular expression to match media fields.
	 */
	const REGEX_MEDIA_FIELD = '#^media_(\d+)_(\w+)$#';

	/**
	 * Extract the field ID from a field string.
	 *
	 * @param string $field The field string to process.
	 *
	 * @return string The extracted field ID.
	 */
	public function getFieldId( $field ) {
		$field_regex = '/^(.*?)__cf(\d+)$/';

		if ( preg_match( $field_regex, $field, $matches ) ) {
			return $matches[1];
		}

		return $field;
	}

	public function extractAttachmentIdAndMediaFields( $field ) {
		if ( ! is_string( $field ) ) {
			return null;
		}

		if ( preg_match( MediaField::REGEX_MEDIA_FIELD, $field, $match ) ) {
			return [
				'attachment_id' => (int) $match[1],
				'media_field'  => $match[2],
			];
		}

		return null;
	}
}
