<?php

namespace WPML\PB\Elementor\Config\DynamicElements\EssentialAddons;

use WPML\FP\Obj;
use WPML\FP\Relation;
use function WPML\FP\compose;

/**
 * @see https://essential-addons.com/elementor/docs/team-member/
 */
class TeamMember {

	/**
	 * @return array
	 */
	public static function get() {
		// $isEATeamMember :: array -> bool
		$isEATeamMember = Relation::propEq( 'widgetType', 'eael-team-member' );

		// $socialLinkLens :: callable -> callable -> mixed
		$socialLinkLens = compose(
			Obj::lensProp( 'settings' ),
			Obj::lensMappedProp( 'eael_team_member_social_profile_links' ),
			Obj::lensPath( [ '__dynamic__', 'link' ] )
		);

		return [ $isEATeamMember, $socialLinkLens, 'popup', 'popup' ];
	}
}
