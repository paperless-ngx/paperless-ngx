import { Component, inject, Input, signal } from '@angular/core'
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

  private tagSignal = signal<Tag>(null)
  private linkTitleSignal = signal('')
  private clickableSignal = signal(false)
  private showParentsSignal = signal(false)
  private _tagID: number

  @Input()
  public set tag(tag: Tag) {
    this.tagSignal.set(tag)
  }

  public get tag(): Tag {
    return this.tagSignal()
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
  get linkTitle(): string {
    return this.linkTitleSignal()
  }

  set linkTitle(linkTitle: string) {
    this.linkTitleSignal.set(linkTitle)
  }

  @Input()
  get clickable(): boolean {
    return this.clickableSignal()
  }

  set clickable(clickable: boolean) {
    this.clickableSignal.set(clickable)
  }

  @Input()
  get showParents(): boolean {
    return this.showParentsSignal()
  }

  set showParents(showParents: boolean) {
    this.showParentsSignal.set(showParents)
  }

  public get loading(): boolean {
    return this.tagService.loading
  }
}
