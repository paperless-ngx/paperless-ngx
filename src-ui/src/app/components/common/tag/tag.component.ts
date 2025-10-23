import { Component, inject, Input } from '@angular/core'
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

  private _tag: Tag
  private _tagID: number

  @Input()
  public set tag(tag: Tag) {
    this._tag = tag
  }

  public get tag(): Tag {
    return this._tag
  }

  @Input()
  set tagID(tagID: number) {
    if (tagID !== this._tagID) {
      this._tagID = tagID
      if (
        this.permissionsService.currentUserCan(
          PermissionAction.View,
          PermissionType.Tag
        )
      ) {
        this.tagService.getCached(this._tagID).subscribe((tag) => {
          this.tag = tag
        })
      }
    }
  }

  @Input()
  linkTitle: string = ''

  @Input()
  clickable: boolean = false

  @Input()
  showParents: boolean = false

  public get loading(): boolean {
    return this.tagService.loading
  }
}
