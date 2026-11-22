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
import { partitionTags, TagPartition } from '../utils/tag-display'

/**
 * Splits a document's tag IDs into regular ones vs those the
 * current user cannot view, see partitionTags.
 */
@Pipe({
  name: 'displayTags',
})
export class DisplayTagsPipe implements PipeTransform {
  private readonly permissionsService = inject(PermissionsService)
  private readonly tagService = inject(TagService)
  private readonly settingsService = inject(SettingsService)

  transform(ids: number[]): Observable<TagPartition> {
    if (!ids?.length) return of({ visible: [], hidden: [] })
    if (
      !this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Tag
      )
    ) {
      return of({ visible: [], hidden: ids })
    }
    return this.tagService.listAll().pipe(
      map((tags) =>
        partitionTags(
          ids,
          new Map<number, Tag>(tags.results.map((t) => [t.id, t])),
          !!this.settingsService.get(SETTINGS_KEYS.TAGS_SHOW_HIERARCHY)
        )
      ),
      catchError(() => of({ visible: ids, hidden: [] }))
    )
  }
}
