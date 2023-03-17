import { Component, Input, Output, EventEmitter } from '@angular/core'
import { DocumentCommentsService } from 'src/app/services/rest/document-comments.service'
import { PaperlessDocumentComment } from 'src/app/data/paperless-document-comment'
import { FormControl, FormGroup } from '@angular/forms'
import { first } from 'rxjs/operators'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'

@Component({
  selector: 'app-document-comments',
  templateUrl: './document-comments.component.html',
  styleUrls: ['./document-comments.component.scss'],
})
export class DocumentCommentsComponent extends ComponentWithPermissions {
  commentForm: FormGroup = new FormGroup({
    newComment: new FormControl(''),
  })

  networkActive = false
  comments: PaperlessDocumentComment[] = []
  newCommentError: boolean = false

  private _documentId: number

  @Input()
  set documentId(id: number) {
    if (id != this._documentId) {
      this._documentId = id
      this.update()
    }
  }

  @Output()
  updated: EventEmitter<number> = new EventEmitter<number>()

  constructor(
    private commentsService: DocumentCommentsService,
    private toastService: ToastService
  ) {
    super()
  }

  update(): void {
    this.networkActive = true
    this.commentsService
      .getComments(this._documentId)
      .pipe(first())
      .subscribe((comments) => {
        this.comments = comments
        this.networkActive = false
      })
  }

  addComment() {
    const comment: string = this.commentForm
      .get('newComment')
      .value.toString()
      .trim()
    if (comment.length == 0) {
      this.newCommentError = true
      return
    }
    this.newCommentError = false
    this.networkActive = true
    this.commentsService.addComment(this._documentId, comment).subscribe({
      next: (result) => {
        this.comments = result
        this.commentForm.get('newComment').reset()
        this.networkActive = false
        this.updated.emit(this.comments.length)
      },
      error: (e) => {
        this.networkActive = false
        this.toastService.showError(
          $localize`Error saving comment: ${e.toString()}`
        )
      },
    })
  }

  deleteComment(commentId: number) {
    this.commentsService.deleteComment(this._documentId, commentId).subscribe({
      next: (result) => {
        this.comments = result
        this.networkActive = false
        this.updated.emit(this.comments.length)
      },
      error: (e) => {
        this.networkActive = false
        this.toastService.showError(
          $localize`Error deleting comment: ${e.toString()}`
        )
      },
    })
  }

  displayName(comment: PaperlessDocumentComment): string {
    if (!comment.user) return ''
    let nameComponents = []
    if (comment.user.first_name) nameComponents.unshift(comment.user.first_name)
    if (comment.user.last_name) nameComponents.unshift(comment.user.last_name)
    if (comment.user.username) {
      if (nameComponents.length > 0)
        nameComponents.push(`(${comment.user.username})`)
      else nameComponents.push(comment.user.username)
    }
    return nameComponents.join(' ')
  }

  commentFormKeydown(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      this.addComment()
    }
  }
}
