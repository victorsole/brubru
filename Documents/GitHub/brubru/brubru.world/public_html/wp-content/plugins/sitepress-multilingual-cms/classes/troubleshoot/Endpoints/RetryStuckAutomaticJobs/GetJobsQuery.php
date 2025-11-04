<?php

namespace WPML\TM\Troubleshooting\Endpoints\RetryStuckAutomaticJobs;

class GetJobsQuery {

	/**
	 * @var \wpdb
	 */
	private $wpdb;

	public function __construct( \wpdb $wpdb ) {
		$this->wpdb = $wpdb;
	}

	/**
	 * @param int $limit
	 *
	 * @return array<array<string, int>>
	 * @throws \Exception
	 */
	public function get( int $limit ) {
		$query = "SELECT
				    wpml_tj.job_id,
				    wpml_tj.rid
				FROM
				    {$this->wpdb->prefix}icl_translate_job wpml_tj
				INNER JOIN {$this->wpdb->prefix}icl_translation_status wpml_ts ON
				    wpml_tj.rid = wpml_ts.rid
				INNER JOIN {$this->wpdb->prefix}icl_translation_batches wpml_tb ON
				    wpml_ts.batch_id = wpml_tb.id
				WHERE
				    wpml_tj.editor = %s AND wpml_tj.revision IS NULL
				  		AND wpml_ts.status = %d AND wpml_ts.translation_service = 'local' 
				  		AND wpml_tb.tp_id IS NULL AND wpml_tb.batch_name LIKE 'Automatic Translations from%'
				LIMIT %d";

		$result = $this->wpdb->get_results(
			$this->wpdb->prepare( $query, \WPML_TM_Editors::NONE, ICL_TM_WAITING_FOR_TRANSLATOR, $limit ),
			ARRAY_A
		);

		if ( $this->wpdb->last_error ) {
			throw new \Exception( $this->wpdb->last_error . ' in ' . __FILE__ . ':' . __LINE__ );
		}

		return $result;
	}

}
