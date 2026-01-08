<?php

/**
 * Class WPML_TM_Batch_Report_Email
 */
class WPML_TM_Batch_Report_Email_Builder {

	const JOBS_LIST_MODE_ASSIGNED  = 'assigned';
	const JOBS_LIST_MODE_AVAILABLE = 'available';
	const JOBS_LIST_MODE_WAITING   = 'waiting';

	/**
	 * @var WPML_TM_Batch_Report
	 */
	private $batch_report;

	/**
	 * @var array
	 */
	private $emails;

	/**
	 * @var WPML_TM_Email_Jobs_Summary_View
	 */
	private $email_template;

	/**
	 * @var int[]
	 */
	private $orphaned_translators_ids;

	/**
	 * @var int[]
	 */
	private $dnd_translators_ids;

	/**
	 * @var array<string,array<string,string>>
	 */
	private $job_list_titles = [];

	/**
	 * WPML_TM_Notification_Batch_Email constructor.
	 *
	 * @param WPML_TM_Batch_Report            $batch_report
	 * @param WPML_TM_Email_Jobs_Summary_View $email_template
	 */
	public function __construct( WPML_TM_Batch_Report $batch_report, WPML_TM_Email_Jobs_Summary_View $email_template ) {
		$this->batch_report             = $batch_report;
		$this->email_template           = $email_template;
		$this->emails                   = array();
		$this->orphaned_translators_ids = [];
		$this->dnd_translators_ids      = [];
	}

	/**
	 * @param string $mode
	 *
	 * @return array<string,string>
	 */
	private function get_jobs_list_titles( $mode ) {
		if ( empty( $this->job_list_titles ) ) {
			$this->job_list_titles = [
				self::JOBS_LIST_MODE_ASSIGNED => [
					'singular' => __( 'You\'ve been assigned a new translation job:', 'wpml-translation-management' ),
					'plural'   => __( 'You\'ve been assigned %s new translation jobs:', 'wpml-translation-management' ),
					'sliced'   => __( 'You\'ve been assigned %2$s new translation jobs (showing the first %1$s):', 'wpml-translation-management' ),
				],
				self::JOBS_LIST_MODE_AVAILABLE => [
					'singular' => __( 'There\'s another new job you can take:', 'wpml-translation-management' ),
					'plural'   => __( 'There are %s other new jobs you can take:', 'wpml-translation-management' ),
					'sliced'   => __( 'There are %2$s other new jobs you can take (showing the first %1$s):', 'wpml-translation-management' ),
				],
				self::JOBS_LIST_MODE_WAITING => [
					'singular' => __( 'There\'s 1 new job waiting for a translator:', 'wpml-translation-management' ),
					'plural'   => __( 'There are %s new jobs waiting for a translator:', 'wpml-translation-management' ),
					'sliced'   => __( 'There are %2$s new jobs waiting for a translator (showing the first %1$s):', 'wpml-translation-management' ),
				],
			];
		}

		return array_key_exists( $mode, $this->job_list_titles ) ? $this->job_list_titles[ $mode ] : $this->job_list_titles[ self::JOBS_LIST_MODE_WAITING ];
	}

	/**
	 * @param array $batch_jobs
	 */
	public function prepare_assigned_jobs_emails( $batch_jobs ) {
		$unassigned_jobs = [];
		if ( array_key_exists( 0, $batch_jobs ) ) {
			$unassigned_jobs = $batch_jobs[0];
		}

		foreach ( $batch_jobs as $translator_id => $language_pairs ) {
			if ( 0 === $translator_id ) {
				continue;
			}

			$translator = get_userdata( $translator_id );
			if ( ! $translator ) {
				$this->orphaned_translators_ids[] = $translator_id;
				continue;
			}

			if ( ! WPML_User_Jobs_Notification_Settings::is_new_job_notification_enabled( $translator_id ) ) {
				$this->dnd_translators_ids[] = $translator_id;
				continue;
			}

			$jobs_list_titles   = $this->get_jobs_list_titles( self::JOBS_LIST_MODE_ASSIGNED );
			$assigned_jobs_body = $this->email_template->render_jobs_list(
				$language_pairs,
				$translator_id,
				$jobs_list_titles['singular'],
				$jobs_list_titles['plural'],
				$jobs_list_titles['sliced']
			);

			if ( null === $assigned_jobs_body ) {
				continue;
			}

			$email = [
				'translator_id' => $translator->ID,
				'email'         => $translator->user_email,
				'subject'       => $this->get_subject_assigned_job(),
				'body'          => '',
				'attachment'    => [],
			];

			$assigned_jobs_for_attachments  = $this->email_template->get_assigned_jobs( true );
			$assignerd_jobs_sliced          = $this->email_template->has_sliced_assigned_jobs();
			$email['body']                  = $this->email_template->render_header( $translator->display_name );
			$email['body']                 .= $assigned_jobs_body;

			$available_jobs_list_titles = $this->get_jobs_list_titles( self::JOBS_LIST_MODE_AVAILABLE );
			$unassigned_jobs_body       = $this->email_template->render_jobs_list(
				$unassigned_jobs,
				$translator_id,
				$available_jobs_list_titles['singular'],
				$available_jobs_list_titles['plural'],
				$available_jobs_list_titles['sliced']
			);

			if ( null !== $unassigned_jobs_body ) {
				$email['body'] .= $unassigned_jobs_body;
			}
			$unassignerd_jobs_sliced = $this->email_template->has_sliced_assigned_jobs();

			if ( $assignerd_jobs_sliced || $unassignerd_jobs_sliced ) {
				$email['body'] .= $this->email_template->render_link_to_jobs();
			}

			$email['body']       .= $this->email_template->render_footer();
			$email['attachment']  = $this->get_attachments( $email, $assigned_jobs_for_attachments );

			$this->emails[] = $email;
		}
	}

	/**
	 * @param array $batch_jobs
	 */
	public function prepare_unassigned_jobs_emails( $batch_jobs ) {
		if ( array_key_exists( 0, $batch_jobs ) ) {

			$unassigned_jobs             = $batch_jobs[0];
			$translators                 = $this->batch_report->get_unassigned_translators( $batch_jobs );
			$unassigned_jobs_list_titles = $this->get_jobs_list_titles( self::JOBS_LIST_MODE_WAITING );

			foreach ( $translators as $translator ) {
				$translator_user = get_userdata( $translator );
				if ( ! $translator_user ) {
					$this->orphaned_translators_ids[] = $translator;
					continue;
				}
				$render_jobs_list = $this->email_template->render_jobs_list(
					$unassigned_jobs,
					$translator_user->ID,
					$unassigned_jobs_list_titles['singular'],
					$unassigned_jobs_list_titles['plural'],
					$unassigned_jobs_list_titles['sliced']
				);

				if ( null !== $render_jobs_list ) {
					$body = $this->email_template->render_header( $translator_user->display_name );
					
					
					$body        .= $render_jobs_list;
					$jobs_sliced  = $this->email_template->has_sliced_assigned_jobs();
					if ( $jobs_sliced ) {
						$body .= $this->email_template->render_link_to_jobs();
					}
					$body .= $this->email_template->render_footer();

					$this->emails[] = array(
						'translator_id' => $translator_user->ID,
						'email'         => $translator_user->user_email,
						'subject'       => $this->get_subject_unassigned_job(),
						'body'          => $body,
					);
				}
			}
		}
	}

	/**
	 * @param array $email
	 * @param array $jobs
	 *
	 * @return string|string[]
	 */
	private function get_attachments( $email, $jobs ) {
		$attachments = array();
		foreach ( $jobs as $job ) {
			if ( 'post' === $job['type'] ) {
				$notificationForNewJob = apply_filters( 'wpml_new_job_notification', $email, $job['job_id'] );
				if ( array_key_exists( 'attachment', $notificationForNewJob ) ) {
					$attachments[] = $notificationForNewJob['attachment'];
				}
			}
		}

		if ( $attachments ) {
			$attachments = apply_filters( 'wpml_new_job_notification_attachments', $attachments );
			if ( count( $attachments ) > 0 ) {
				$attachment_values = array_values( $attachments );
				return $attachment_values[0];
			}
		}

		return [];
	}

	/**
	 * @return string
	 */
	private function get_subject_assigned_job() {
		return sprintf( __( 'New translation job from %s', 'wpml-translation-management' ), get_bloginfo( 'name' ) );
	}

	/**
	 * @return string
	 */
	private function get_subject_unassigned_job() {
		return sprintf( __( 'Job waiting for a translator in %s', 'wpml-translation-management' ), get_bloginfo( 'name' ) );
	}

	/**
	 * @return array
	 */
	public function get_emails() {
		return $this->emails;
	}

	/**
	 * @return array
	 */
	public function get_orphaned_translators_ids() {
		return $this->orphaned_translators_ids;
	}

	/**
	 * @return array
	 */
	public function get_dnd_translators_ids() {
		return $this->dnd_translators_ids;
	}

}