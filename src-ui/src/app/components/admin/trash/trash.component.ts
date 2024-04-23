import { HttpClient } from '@angular/common/http'
import { Component } from '@angular/core'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { ToastService } from 'src/app/services/toast.service'
import { TrashService } from 'src/app/services/trash.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-trash',
  templateUrl: './trash.component.html',
  styleUrl: './trash.component.scss',
})
export class TrashComponent {
  public trashedObjects: ObjectWithId[] = []
  public selectedObjects: Set<number> = new Set()
  public togggleAll: boolean = false
  public page: number = 1
  public isLoading: boolean = false

  constructor(
    private trashService: TrashService,
    private toastService: ToastService
  ) {
    this.reload()
  }

  reload() {
    this.isLoading = true
    this.trashService.getTrash().subscribe((trash) => {
      this.trashedObjects = trash
      this.isLoading = false
      console.log('Trash:', trash)
    })
  }

  deleteObject(object: ObjectWithId) {
    this.trashService.emptyTrash([object.id]).subscribe(() => {
      this.toastService.showInfo($localize`Object deleted`)
      this.reload()
    })
  }

  emptyTrash(objects: Set<number> = null) {
    console.log('Emptying trash')
    this.trashService
      .emptyTrash(objects ? Array.from(objects) : [])
      .subscribe(() => {
        this.toastService.showInfo($localize`Object(s) deleted`)
        this.reload()
      })
  }

  restoreObject(object: ObjectWithId) {
    this.trashService.restoreObjects([object.id]).subscribe(() => {
      this.toastService.showInfo($localize`Object restored`)
      this.reload()
    })
  }

  restoreAll(objects: Set<number> = null) {
    this.trashService
      .restoreObjects(objects ? Array.from(this.selectedObjects) : [])
      .subscribe(() => {
        this.toastService.showInfo($localize`Object(s) restored`)
        this.reload()
      })
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedObjects = new Set(this.trashedObjects.map((t) => t.id))
    } else {
      this.clearSelection()
    }
  }

  toggleSelected(object: ObjectWithId) {
    this.selectedObjects.has(object.id)
      ? this.selectedObjects.delete(object.id)
      : this.selectedObjects.add(object.id)
  }

  clearSelection() {
    this.togggleAll = false
    this.selectedObjects.clear()
  }
}
