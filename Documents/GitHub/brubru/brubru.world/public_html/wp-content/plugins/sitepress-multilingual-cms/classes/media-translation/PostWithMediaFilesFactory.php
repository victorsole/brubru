<?php

namespace WPML\MediaTranslation;

class PostWithMediaFilesFactory {
	public function create( $post_id ) {
		global $sitepress, $iclTranslationManagement;

		$media_img_parse = new MediaImgParse();

		return new PostWithMediaFiles(
			$post_id,
			$media_img_parse,
			new MediaAttachmentByUrlFactory(),
			$sitepress,
			new \WPML_Custom_Field_Setting_Factory( $iclTranslationManagement ),
			new CopiedAndReferencedMediaExtractor(
				$media_img_parse,
				$sitepress
			),
			new UsageOfMediaFilesInPosts()
		);
	}
}