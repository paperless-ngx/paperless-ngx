import { ObjectWithId } from './object-with-id'
import { PaperlessCorrespondent } from './paperless-correspondent'
import { PaperlessDocumentType } from './paperless-document-type'
import { PaperlessMailAccount } from './paperless-mail-account'
import { PaperlessTag } from './paperless-tag'

export enum MailFilterAttachmentType {
  Attachments = 1,
  Everything = 2,
}

export const MailFilterAttachmentTypeOptions: Array<{
  id: number
  name: string
}> = [
  {
    id: MailFilterAttachmentType.Attachments,
    name: $localize`Only process attachments.`,
  },
  {
    id: MailFilterAttachmentType.Everything,
    name: $localize`Process all files, including 'inline' attachments.`,
  },
]

export enum MailAction {
  Delete = 1,
  Move = 2,
  MarkRead = 3,
  Flag = 4,
  Tag = 5,
}

export const MailActionOptions: Array<{ id: number; name: string }> = [
  { id: MailAction.Delete, name: $localize`Delete` },
  { id: MailAction.Move, name: $localize`Move to specified folder` },
  {
    id: MailAction.MarkRead,
    name: $localize`Mark as read, don't process read mails`,
  },
  {
    id: MailAction.Flag,
    name: $localize`Flag the mail, don't process flagged mails`,
  },
  {
    id: MailAction.Tag,
    name: $localize`Tag the mail with specified tag, don't process tagged mails`,
  },
]

export enum MailMetadataTitleOption {
  FromSubject = 1,
  FromFilename = 2,
}

export const MailMetadataTitleOptionOptions: Array<{
  id: number
  name: string
}> = [
  {
    id: MailMetadataTitleOption.FromSubject,
    name: $localize`Use subject as title`,
  },
  {
    id: MailMetadataTitleOption.FromFilename,
    name: $localize`Use attachment filename as title`,
  },
]

export enum MailMetadataCorrespondentOption {
  FromNothing = 1,
  FromEmail = 2,
  FromName = 3,
  FromCustom = 4,
}

export const MailMetadataCorrespondentOptionOptions: Array<{
  id: number
  name: string
}> = [
  {
    id: MailMetadataCorrespondentOption.FromNothing,
    name: $localize`Do not assign a correspondent`,
  },
  {
    id: MailMetadataCorrespondentOption.FromEmail,
    name: $localize`Use mail address`,
  },
  {
    id: MailMetadataCorrespondentOption.FromName,
    name: $localize`Use name (or mail address if not available)`,
  },
  {
    id: MailMetadataCorrespondentOption.FromCustom,
    name: $localize`Use correspondent selected below`,
  },
]

export interface PaperlessMailRule extends ObjectWithId {
  name: string

  order: number

  account: PaperlessMailAccount

  folder: string

  filter_from: string

  filter_subject: string

  filter_body: string

  filter_attachment_filename: string

  maximum_age: number

  attachment_type: MailFilterAttachmentType

  action: MailAction

  action_parameter?: string

  assign_title_from: MailMetadataTitleOption

  assign_tags?: PaperlessTag[]

  assign_document_type?: PaperlessDocumentType

  assign_correspondent_from?: MailMetadataCorrespondentOption

  assign_correspondent?: PaperlessCorrespondent
}
