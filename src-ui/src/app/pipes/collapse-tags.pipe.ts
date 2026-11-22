import { inject, Pipe, PipeTransform } from '@angular/core'
import { catchError, map, Observable, of } from 'rxjs'
import { Tag } from '../data/tag'
import { SETTINGS_KEYS } from '../data/ui-settings'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'
import { TagService } from '../services/rest/tag.service'
import { SettingsService } from '../services/settings.service'
import { collapseImpliedAncestors } from '../utils/collapse-tags'

/**
 * Drops tag IDs whose descendant is also in the list for when the child's
 * Tag badge already shows its parent.
 */
@Pipe({
  name: 'collapseTags',
})
export class CollapseTagsPipe implements PipeTransform {
  private readonly permissionsService = inject(PermissionsService)
  private readonly tagService = inject(TagService)
  private readonly settingsService = inject(SettingsService)

  transform(ids: number[]): Observable<number[]> {
    if (
      !ids?.length ||
      !this.settingsService.get(SETTINGS_KEYS.TAGS_SHOW_HIERARCHY) ||
      !this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Tag
      )
    ) {
      return of(ids ?? [])
    }
    return this.tagService.listAll().pipe(
      map((tags) =>
        collapseImpliedAncestors(
          ids,
          new Map<number, Tag>(tags.results.map((t) => [t.id, t]))
        )
      ),
      catchError(() => of(ids))
    )
  }
}
