import { Component, Input, ViewChild, forwardRef } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { AbstractInputComponent } from '../abstract-input'
import {
  CdkDragDrop,
  CdkDropList,
  moveItemInArray,
} from '@angular/cdk/drag-drop'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DragDropSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-drag-drop-select',
  templateUrl: './drag-drop-select.component.html',
  styleUrl: './drag-drop-select.component.scss',
})
export class DragDropSelectComponent extends AbstractInputComponent<string[]> {
  @Input() title: string = $localize`Selected items`

  @Input() items: { id: string; name: string }[] = []
  public selectedItems: { id: string; name: string }[] = []

  @Input()
  emptyText = $localize`No items selected`

  @ViewChild('selectedList') selectedList: CdkDropList
  @ViewChild('unselectedList') unselectedList: CdkDropList

  get unselectedItems(): { id: string; name: string }[] {
    return this.items.filter((i) => !this.selectedItems.includes(i))
  }

  writeValue(newValue: string[]): void {
    super.writeValue(newValue)
    this.selectedItems =
      newValue
        ?.map((id) => this.items.find((i) => i.id === id))
        .filter((item) => item) ?? []
  }

  public drop(event: CdkDragDrop<string[]>) {
    if (
      event.previousContainer === event.container &&
      event.container === this.selectedList
    ) {
      moveItemInArray(
        this.selectedItems,
        event.previousIndex,
        event.currentIndex
      )
    } else if (event.container === this.selectedList) {
      this.selectedItems.splice(
        event.currentIndex,
        0,
        this.unselectedItems[event.previousIndex]
      )
    } else if (
      event.container === this.unselectedList &&
      event.previousContainer === this.selectedList
    ) {
      this.selectedItems.splice(event.previousIndex, 1)
    }
    this.onChange(this.selectedItems.map((i) => i.id))
  }
}
