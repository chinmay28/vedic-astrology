package io.github.chinmay28.kundali

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.app.Activity
import android.graphics.Typeface
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.animation.LinearInterpolator
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import com.google.android.material.imageview.ShapeableImageView
import com.google.android.material.shape.ShapeAppearanceModel
import io.github.chinmay28.kundali.core.DevFlash
import kotlin.math.min

/**
 * The developer badge thrown up full screen for a beat, natively — the web
 * page's `.dev-flash`, on the same 3-second clock ([DevFlash] holds the
 * keyframes). A tap anywhere ends it early.
 */
object DevFlashOverlay {
    fun show(activity: Activity) {
        val content = activity.findViewById<ViewGroup>(android.R.id.content)
        if (content.findViewWithTag<View>(TAG) != null) return
        val density = activity.resources.displayMetrics.density
        val metrics = activity.resources.displayMetrics
        // min(64vmin, 22rem), as on the page.
        val size = min(min(metrics.widthPixels, metrics.heightPixels) * 0.64f, 352 * density).toInt()

        val badge = ShapeableImageView(activity).apply {
            setImageResource(R.drawable.dev_badge_full)
            contentDescription = activity.getString(R.string.dev_badge_full)
            shapeAppearanceModel = ShapeAppearanceModel.builder().setAllCornerSizes(size / 2f).build()
            elevation = 18 * density
        }
        val handle = TextView(activity).apply {
            text = DevFlash.HANDLE
            typeface = Typeface.MONOSPACE
            textSize = 13f
            letterSpacing = 0.06f
            setTextColor(activity.getColor(R.color.kundali_gold))
            gravity = Gravity.CENTER
        }
        val lockup = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            addView(badge, LinearLayout.LayoutParams(size, size))
            addView(handle, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                topMargin = (16 * density).toInt()
            })
        }
        val veil = FrameLayout(activity).apply {
            tag = TAG
            setBackgroundColor(activity.getColor(R.color.dev_flash_veil))
            isClickable = true
            alpha = 0f
            addView(lockup, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        }
        content.addView(veil, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))

        val remove = { (veil.parent as? ViewGroup)?.removeView(veil) }
        if (!ValueAnimator.areAnimatorsEnabled()) {
            // Animations are off on this phone: show it still, for as long.
            veil.alpha = 1f
            veil.setOnClickListener { remove() }
            veil.postDelayed({ remove() }, DevFlash.DURATION_MS)
            return
        }
        val clock = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = DevFlash.DURATION_MS
            interpolator = LinearInterpolator()
            addUpdateListener {
                val f = it.animatedValue as Float
                veil.alpha = DevFlash.veilAlpha(f)
                val s = DevFlash.badgeScale(f)
                lockup.scaleX = s
                lockup.scaleY = s
            }
            addListener(object : AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: Animator) {
                    remove()
                }
            })
        }
        veil.setOnClickListener { clock.cancel() }
        clock.start()
    }

    private const val TAG = "dev-flash"
}
