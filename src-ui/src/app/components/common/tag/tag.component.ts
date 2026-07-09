import { Component, effect, inject, input, model } from '@angular/core'
import { Tag } from 'src/app/data/tag'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { TagService } from 'src/app/services/rest/tag.service'

@Component({
  selector: 'pngx-tag',
  templateUrl: './tag.component.html',
  styleUrls: ['./tag.component.scss'],
})
export class TagComponent {
  private permissionsService = inject(PermissionsService)
  private tagService = inject(TagService)

  readonly tag = model<Tag>(null)
  readonly tagID = input<number>(undefined)
  readonly linkTitle = input('')
  readonly clickable = input(false, {
    transform: (value: boolean | string) =>
      value === '' || value === true || value === 'true',
  })
  readonly showParents = input(false)

  constructor() {
    effect(() => {
      const tagID = this.tagID()
      if (tagID) {
        if (
          this.permissionsService.currentUserCan(
            PermissionAction.View,
            PermissionType.Tag
          )
        ) {
          this.tagService.getCached(tagID).subscribe((tag) => {
            this.tag.set(tag)
          })
        }
      }
    })
  }

  public get loading(): boolean {
    return this.tagService.loading
  }
}
