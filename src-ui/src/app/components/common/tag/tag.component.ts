import {
  Component,
  computed,
  effect,
  inject,
  input,
  model,
  output,
  signal,
} from '@angular/core'
import { Tag } from 'src/app/data/tag'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { SettingsService } from 'src/app/services/settings.service'
import { getTagAncestors } from 'src/app/utils/tag-display'

const FOCUS_ANIMATION_MS = 200
// matches the .split-parent min-width in tag.component.scss
const COLLAPSE_BELOW_EM = 1.5

@Component({
  selector: 'pngx-tag',
  templateUrl: './tag.component.html',
  styleUrls: ['./tag.component.scss'],
})
export class TagComponent {
  private readonly permissionsService = inject(PermissionsService)
  private readonly tagService = inject(TagService)
  private readonly settingsService = inject(SettingsService)

  readonly tag = model<Tag>(null)
  readonly tagID = input<number>(undefined)
  readonly linkTitle = input('')
  readonly clickable = input(false, {
    transform: (value: boolean | string) =>
      value === '' || value === true || value === 'true',
  })

  readonly split = input(false)

  readonly parentClick = output<number>()

  private readonly ancestors = signal<Tag[]>([])

  public get ancestorSegments(): Tag[] {
    return this.split() &&
      this.settingsService.get(SETTINGS_KEYS.TAGS_SHOW_HIERARCHY)
      ? this.ancestors()
      : []
  }

  public readonly path = computed(() =>
    [...this.ancestors(), this.tag()]
      .filter(Boolean)
      .map((t) => t.name)
      .join(' › ')
  )

  constructor() {
    effect(() => {
      const tagID = this.tagID()
      if (tagID && this.canViewTags) {
        this.tagService.getCached(tagID).subscribe((tag) => {
          this.tag.set(tag)
        })
      }
    })

    // ancestors for split badges, from either tagID or a passed-in tag
    effect(() => {
      const id = this.tagID() || this.tag()?.id
      if (!this.split() || !id || !this.canViewTags) {
        this.ancestors.set([])
        return
      }
      this.tagService.listAll().subscribe((tags) => {
        this.ancestors.set(
          getTagAncestors(
            id,
            new Map<number, Tag>(tags.results.map((t) => [t.id, t]))
          )
        )
      })
    })
  }

  private get canViewTags(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.Tag
    )
  }

  public get loading(): boolean {
    return this.tagService.loading
  }

  /**
   * Gives the hovered segment priority (.focused class, see scss)
   * and animates each from old width to new
   */
  setFocus(segment: HTMLElement, focused: HTMLElement | null) {
    const segments = Array.from(segment.children) as HTMLElement[]
    const before = segments.map((s) => s.getBoundingClientRect().width)
    for (const segment of segments) {
      segment.getAnimations().forEach((a) => a.cancel())
      segment.classList.toggle('focused', segment === focused)
    }
    const after = segments.map((s) => s.getBoundingClientRect().width)

    segments.forEach((segment, i) => {
      const em = Number.parseFloat(getComputedStyle(segment).fontSize)
      segment.classList.toggle(
        'collapsed',
        !!focused &&
          segment.classList.contains('split-parent') &&
          after[i] < COLLAPSE_BELOW_EM * em
      )
      if (Math.abs(after[i] - before[i]) < 0.5) return
      segment.animate(
        [
          { flex: `0 0 ${before[i]}px`, minWidth: 0 },
          { flex: `0 0 ${after[i]}px`, minWidth: 0 },
        ],
        { duration: FOCUS_ANIMATION_MS, easing: 'ease' }
      )
    })
  }

  onParentClick(event: MouseEvent, id: number) {
    event.preventDefault()
    event.stopImmediatePropagation()
    this.parentClick.emit(id)
  }
}
