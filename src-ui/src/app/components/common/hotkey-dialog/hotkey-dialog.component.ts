import { Component, inject } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'

const SYMBOLS = {
  meta: '&#8984;', // ⌘
  control: '&#8963;', // ⌃
  shift: '&#8679;', // ⇧
  left: '&#8592;', // ←
  right: '&#8594;', // →
  up: '&#8593;', // ↑
  down: '&#8595;', // ↓
  arrowleft: '&#8592;', // ←
  arrowright: '&#8594;', // →
}

@Component({
  selector: 'pngx-hotkey-dialog',
  templateUrl: './hotkey-dialog.component.html',
  styleUrl: './hotkey-dialog.component.scss',
})
export class HotkeyDialogComponent {
  activeModal = inject(NgbActiveModal)

  public title: string = $localize`Keyboard shortcuts`
  public hotkeys: Map<string, string> = new Map()

  public close(): void {
    this.activeModal.close()
  }

  public formatKey(key: string, macOS: boolean = false): string {
    if (macOS) {
      key = key.replace('control', 'meta')
    }
    return key
      .split('.')
      .map((k) => SYMBOLS[k] || k)
      .join(' ')
  }
}
