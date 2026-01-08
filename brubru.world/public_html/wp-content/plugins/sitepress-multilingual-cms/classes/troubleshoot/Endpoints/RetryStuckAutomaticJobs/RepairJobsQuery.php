<?php

namespace WPML\TM\Troubleshooting\Endpoints\RetryStuckAutomaticJobs;

class RepairJobsQuery {

	/**
	 * @var \wpdb
	 */
	private $wpdb;

	public function __construct( \wpdb $wpdb ) {
		$this->wpdb = $wpdb;
	}

	/**
	 * @param array<array<string, int>> $data
	 *
	 * @return bool
	 * @throws \Exception
	 */
	public function repair( array $data ): bool {
		$result = $this->repairJobs( array_column( $data, 'job_id' ) );

		return $result && $this->repairJobsStatus( array_column( $data, 'rid' ) );
	}

	/**
	 * @param int[] $jobIds
	 *
	 * @return bool
	 * @throws \Exception
	 */
	private function repairJobs( array $jobIds ): bool {
		$result = (bool) $this->wpdb->query(
			"UPDATE {$this->wpdb->prefix}icl_translate_job 
					SET editor = '" . \WPML_TM_Editors::ATE . "', automatic = 1 
					WHERE job_id IN ( " . wpml_prepare_in( $jobIds, '%d' ) . ")"
		);

		if ( $this->wpdb->last_error ) {
			throw new \Exception( $this->wpdb->last_error . ' in ' . __FILE__ . ':' . __LINE__ );
		}

		return $result;
	}

	/**
	 * @param int[] $rids
	 *
	 * @return bool
	 * @throws \Exception
	 */
	private function repairJobsStatus( array $rids ): bool {
		$result = (bool) $this->wpdb->query(
			"UPDATE {$this->wpdb->prefix}icl_translation_status 
					SET status = '" . ICL_TM_ATE_NEEDS_RETRY . "'
					WHERE rid IN ( " . wpml_prepare_in( $rids, '%d' ) . ")"
		);

		if ( $this->wpdb->last_error ) {
			throw new \Exception( $this->wpdb->last_error . ' in ' . __FILE__ . ':' . __LINE__ );
		}

		return $result;
	}

}
