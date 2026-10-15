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
          <!-- 如果CSS设置的尺寸比属性设置的尺寸还大，在图片加载完后布局会变化，可能导致滚动卡住，没什么好的解决方法 -->
          <img :key="index" v-else-if="content.type === CONTENT_PART_TYPE_IMAGE"
            class="emoji yt-formatted-string style-scope yt-live-chat-text-message-renderer"
            :src="content.url" :alt="content.text" :shared-tooltip-text="content.text" :id="`emoji-${content.text}`"
            :width="content.width" :height="content.height"
            :class="{ 'blc-large-emoji': content.height >= 100 }"
          >
        </template>

      </span>
      <ul v-if="translations && translations.length" class="translation-list" aria-label="多语言译文">
        <li v-for="row in translations" :key="row.language" :lang="row.language" :data-language="row.language" :data-status="row.status" class="translation-row">
          <span class="translation-language">{{ row.language }}</span>
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
      CONTENT_PART_TYPE_TEXT: constants.CONTENT_PART_TYPE_TEXT,
      CONTENT_PART_TYPE_IMAGE: constants.CONTENT_PART_TYPE_IMAGE
    }
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
