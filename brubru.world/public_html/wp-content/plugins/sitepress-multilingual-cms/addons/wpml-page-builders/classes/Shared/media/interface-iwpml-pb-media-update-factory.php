<?php

interface IWPML_PB_Media_Update_Factory {

	/**
	 * @param boolean $find_usage_instead_of_translate
	 *
	 * @return IWPML_PB_Media_Update
	 */
	public function create( $find_usage_instead_of_translate = false );
}
