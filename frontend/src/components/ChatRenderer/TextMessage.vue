<template>
  <yt-live-chat-text-message-renderer :author-type="authorTypeText" :blc-guard-level="privilegeType" :data-message-id="messageId">
    <img-shadow id="author-photo" height="24" width="24" class="style-scope yt-live-chat-text-message-renderer"
      :imgUrl="avatarUrl"
    ></img-shadow>
    <div id="content" class="style-scope yt-live-chat-text-message-renderer">
      <span id="timestamp" class="style-scope yt-live-chat-text-message-renderer">{{ timeText }}</span>
      <author-chip class="style-scope yt-live-chat-text-message-renderer"
        :isInMemberMessage="false" :authorName="authorName" :authorType="authorType" :privilegeType="privilegeType"
      ></author-chip><span class="author-separator" aria-hidden="true">: </span>
      <span id="message" class="style-scope yt-live-chat-text-message-renderer">
        <template v-for="(content, index) in contentParts">
          <span :key="index" v-if="content.type === CONTENT_PART_TYPE_TEXT">{{ content.text }}</span>
          <span :key="index" v-else-if="content.type === CONTENT_PART_TYPE_IMAGE" class="emote-part" :class="{ 'sticker-part': content.kind === 'sticker' }">
            <img v-if="!failedImages[content.url]" class="emoji yt-formatted-string style-scope yt-live-chat-text-message-renderer"
              :class="{ 'chat-sticker': content.kind === 'sticker' }" :src="content.url" :alt="content.text" :title="content.text"
              :width="content.width" :height="content.height" :style="imageStyle(content)" referrerpolicy="no-referrer"
              @load="$emit('content-resize')" @error="imageFailed(content.url)">
            <span v-else class="emote-fallback" :title="'表情图片加载失败'">{{ content.text }}</span>
          </span>
        </template>

      </span>
      <ul v-if="translations && translations.length" class="translation-list" aria-label="多语言译文">
        <li v-for="row in translations" :key="row.language" :lang="row.language" :data-language="row.language" :data-status="row.status" class="translation-row">
          <span v-if="row.text" class="translation" dir="auto">{{ row.text }}</span>
          <span v-else class="translation-placeholder">{{ row.status === 'pending' ? '翻译中…' : row.status === 'failed' ? '翻译暂不可用' : row.reason === 'demo_unsupported' ? '演示暂无该语言样例' : '已跳过' }}</span>
        </li>
      </ul>
      <span v-else-if="translation" class="translation" dir="auto">{{ translation }}</span>
    </div>
  </yt-live-chat-text-message-renderer>
</template>

<script>
import ImgShadow from './ImgShadow'
import AuthorChip from './AuthorChip'
import * as constants from './constants'
import * as utils from '@/utils'

// HSL
const REPEATED_MARK_COLOR_START = [210, 100.0, 62.5]
const REPEATED_MARK_COLOR_END = [360, 87.3, 69.2]

export default {
  name: 'TextMessage',
  components: {
    ImgShadow,
    AuthorChip
  },
  props: {
    avatarUrl: String,
    translation: String,
    translations: Array,
    messageId: String,
    time: Date,
    authorName: String,
    authorType: Number,
    contentParts: Array,
    privilegeType: Number,
    repeated: Number
  },
  data() {
    return {
      failedImages: {},
      CONTENT_PART_TYPE_TEXT: constants.CONTENT_PART_TYPE_TEXT,
      CONTENT_PART_TYPE_IMAGE: constants.CONTENT_PART_TYPE_IMAGE
    }
  },
  methods: {
    imageStyle(part) {
      const size = part.kind === 'sticker' ? 4 : 1.35
      const ratio = Math.max(.25, Math.min(4, part.width / part.height))
      return { height: `${size}em`, width: `${size * ratio}em`, maxHeight: part.kind === 'sticker' ? '160px' : 'none',
        maxWidth: part.kind === 'sticker' ? 'min(100%, 256px)' : '5.4em', objectFit: 'contain', verticalAlign: 'middle' }
    },
    imageFailed(url) { this.$set(this.failedImages, url, true); this.$emit('content-resize') }
  },
  computed: {
    timeText() {
      return utils.getTimeTextHourMin(this.time)
    },
    authorTypeText() {
      return constants.AUTHOR_TYPE_TO_TEXT[this.authorType]
    },
    repeatedMarkColor() {
      let color
      if (this.repeated <= 2) {
        color = REPEATED_MARK_COLOR_START
      } else if (this.repeated >= 10) {
        color = REPEATED_MARK_COLOR_END
      } else {
        color = [0, 0, 0]
        let t = (this.repeated - 2) / (10 - 2)
        for (let i = 0; i < 3; i++) {
          color[i] = REPEATED_MARK_COLOR_START[i] + ((REPEATED_MARK_COLOR_END[i] - REPEATED_MARK_COLOR_START[i]) * t)
        }
      }
      return `hsl(${color[0]}, ${color[1]}%, ${color[2]}%)`
    }
  }
}
</script>

<style scoped>
#message >>> .el-badge {
  margin-left: 10px;
}

#message >>> .el-badge__content {
  font-size: 12px !important;
  line-height: 18px !important;
  text-shadow: none !important;
  font-family: sans-serif !important;
  color: #FFF !important;
  background-color: var(--repeated-mark-color) !important;
  border: none;
}
</style>

<style src="@/assets/css/youtube/yt-live-chat-text-message-renderer.css"></style>
